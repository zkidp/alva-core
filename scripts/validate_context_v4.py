"""Read-only post-run evidence validation, added after generation.

Never imports/launches a model, modifies frozen runtime or prints thoughts.
Its output contains hashes and counts only. Private raw records are required.
"""
import argparse
import copy
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from benchmarks.compact_deepseek.api import totals,usage
from integrations.benchmark_runtime_v2.freeze import decode
from integrations.codex.maintenance_host import sha,canonical


def slot(record,backend,frozen):
    entry=record;task=frozen['tasks'][entry['task']]
    original=decode(task['bundle'],task['bundle']['payload_sha256'])
    user={'task':task['public_task'],'source_paths':list(original)}
    if entry['arm']=='V3':user['source_files']={p:b.decode() for p,b in original.items()}
    initial=[{'role':'system','content':frozen['developer_instructions']+'\nCondition: '+entry['arm']+
        '\nActive official profile:\n'+frozen['docs']['SKILL.md' if entry['arm']=='V3' else 'host_skill']},
        {'role':'user','content':json.dumps(user,ensure_ascii=False)}]
    source_state=copy.deepcopy(original)
    assert record['initial_messages']==initial,'INITIAL_PUBLIC_INPUT_CHANGED'
    assert record['valid'] and record['correct'] and record['terminal_confirmed']
    assert record['submitted_chat_requests']==len(record['responses'])
    events=record['tool_events'];index=0;observed=0;messages=copy.deepcopy(initial);reports=[]
    for response in record['responses']:
        payload={'model':frozen['model'],'messages':messages,'tools':frozen['provider_tools'][entry['arm']],**frozen['api_parameters']}
        assert sha(canonical(payload))==response['request_sha256'],'REQUEST_HISTORY_OR_SCHEMA_CHANGED'
        raw=response['response'];assert raw['model']==frozen['model']
        reports.append(usage(raw['usage']))
        message=raw['choices'][0]['message'];calls=message.get('tool_calls',[]);observed+=len(calls)
        if calls:messages.append(message)
        for call in calls:
            if index==len(events):break # Successful publication ends the frozen slot.
            event=events[index];index+=1
            assert call['function']['name']==event['name'],'TOOL_DISPATCH_MISMATCH'
            try:args=json.loads(call['function']['arguments'])
            except (ValueError,TypeError):args=None
            assert args==event['arguments'],'OPERATOR_TOOL_ARGUMENT_CHANGED'
            messages.append({'role':'tool','tool_call_id':call['id'],
                'content':json.dumps(event['response'],ensure_ascii=False)})
            value=event['response'].get('structuredContent',event['response'])
            if event['name']=='read_reference' and value.get('content') is not None:
                from integrations.codex.maintenance_context import sectioned
                text=frozen['docs'][args['document']]
                assert value['content']==(text if args['section']=='all' else sectioned(text)[args['section']]),'REFERENCE_DRIFT'
            if event['name']=='read_source' and value.get('status')=='SOURCE':
                from integrations.codex.maintenance_context import source_read
                assert value==source_read(source_state,args,'ACKNOWLEDGED_SOURCE_PROPOSAL' if entry['arm']=='T' else 'IMPORT_SOURCE_NOT_STAGED_AIR'),'SOURCE_FEEDBACK_DRIFT'
            if event['name']=='prepare_change' and entry['arm']=='T' and value.get('source_edits_applied'):
                for edit in args['edits']:
                    text=source_state[edit['path']].decode();assert text.count(edit['old'])==1
                    source_state[edit['path']]=text.replace(edit['old'],edit['new'],1).encode()

    assert index==len(events)==record['dispatched_tool_calls'] and observed==record['observed_tool_calls']
    assert reports==record['usage_reports'] and totals(reports)==record['reported_usage'],'USAGE_ACCOUNTING_CHANGED'
    assert all(u['inputTokens']+u['outputTokens']==u['totalTokens'] and
        0<=u['cachedInputTokens']<=u['inputTokens'] for u in reports),'INVALID_PROVIDER_USAGE_CATEGORIES'
    assert sha(canonical(backend))==record['backend_sha256'],'BACKEND_RECEIPT_CHANGED'
    assert backend['correct'] and backend['task']==backend['regression']=='PASS'
    assert backend['original_sources_unchanged'] and backend['cleanup_confirmed'] and backend['fresh_authority_matches']
    commits=[e for e in backend['calls'] if e['name']=='publish_change' and e['trusted_result'].get('status')=='PUBLISHED']
    assert len(commits)==backend['successful_publications']==1,'MISSING_OR_MULTIPLE_NATIVE_PUBLICATIONS'
    commit=commits[0];published=commit['trusted_result']
    prepared=[e['trusted_result'] for e in backend['calls'] if e['name']=='prepare_change' and
        e['trusted_result'].get('proposal_id')==commit['arguments']['proposal_id']]
    assert len(prepared)==1 and prepared[0]['status']=='PREPARED'
    receipt=prepared[0]['test_receipt']
    assert published['test_receipt_sha256']==receipt['receipt_sha256'],'UNBOUND_TEST_RECEIPT'
    tested=[r for r in backend['evaluations'] if sha(canonical(r))==receipt['receipt_sha256']]
    assert len(tested)==1 and tested[0]['status']=='PASS'
    assert tested[0]['checks']=={'check':'PASS','build':'PASS','test':'PASS'}
    assert tested[0]['tested_snapshot_sha256']==receipt['snapshot_sha256'],'DIFFERENT_DRAFT_TESTED'
    assert tested[0]['project_revision']==published['commit']['revision'],'TESTED_AND_COMMITTED_REVISION_DIFFER'
    assert backend['scope']==published['commit']['host_scope'],'FRESH_SCOPE_AND_COMMIT_SCOPE_DIFFER'
    assert backend['scope']['status']=='SCOPE_ALLOWED' and backend['scope']['changed_functions']==[task['public_task']['target']]
    assert backend['scope']['unauthorized_functions']==[]
    return {'id':record['id'],'status':'PASS','requests_verified':len(reports),
        'backend_sha256':record['backend_sha256'],'actual_native_commits':1,
        'fresh_scope_matches_commit':True,'independent_task':'PASS','independent_regression':'PASS'}


def main(args):
    frozen=json.loads((ROOT/'benchmarks/context_v4/FREEZE.json').read_bytes())
    raw=json.loads((args.directory/'RESULTS.json').read_bytes())
    assert raw['status']=='COMPLETED' and len(raw['rows'])==12
    assert [(r['id'],r['task'],r['arm']) for r in raw['rows']]==[(r['id'],r['task'],r['arm']) for r in frozen['schedule']]
    rows=[];first=None
    for record in raw['rows']:
        backend=json.loads((args.directory/record['id']/'backend.json').read_bytes())
        rows.append(slot(record,backend,frozen))
        if first is None:first=(record,backend)
    assert sum(r['requests_verified'] for r in rows)==raw['submitted_chat_requests']
    negative=[]
    for label in ('initial_input','cached_subtraction','tool_argument','backend_receipt'):
        record,backend=copy.deepcopy(first)
        if label=='initial_input':record['initial_messages'][1]['content']+=' injected'
        elif label=='cached_subtraction':record['reported_usage']['totalTokens']-=record['reported_usage']['cachedInputTokens']
        elif label=='tool_argument':record['tool_events'][0]['arguments']={'function':'unauthorized'}
        else:backend['scope']['status']='SCOPE_VIOLATION'
        try:slot(record,backend,frozen)
        except AssertionError:negative.append(label)
        else:raise AssertionError('TAMPER_CONTROL_NOT_DETECTED:'+label)
    for p,h in frozen['local_runtime_files'].items():
        assert sha((ROOT/p).read_bytes())==h,'FROZEN_RUNTIME_MODIFIED:'+p
    result={'status':'PASS','postrun_validator_sha256':sha(Path(__file__).read_bytes()),
        'freeze_sha256':raw['freeze_sha256'],'slots':len(rows),'requests_verified':sum(r['requests_verified'] for r in rows),
        'actual_native_commits':sum(r['actual_native_commits'] for r in rows),
        'frozen_runtime_files_unchanged':len(frozen['local_runtime_files']),
        'tamper_controls_detected':negative,'model_generation_calls':0,'rows':rows}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);p.add_argument('--output',type=Path,required=True)
    main(p.parse_args())
