"""Public aggregate acceptance report; never copies messages or reasoning."""
import argparse
import json
from pathlib import Path
import statistics

from benchmarks.compact_deepseek.api import totals
from benchmarks.context_v4.protocol import HERE
from benchmarks.context_v4.runner import save
from integrations.codex.maintenance_host import sha


def analyze(directory):
    raw=json.loads((directory/'RESULTS.json').read_bytes())
    frozen=json.loads((HERE/'FREEZE.json').read_bytes())
    rows=[]
    keys=('id','task','arm','valid','correct','model_sessions_started','terminal_confirmed','stop_reason',
        'active_seconds','setup_seconds','finalization_seconds','reported_usage','usage_complete','submitted_chat_requests','observed_tool_calls',
        'dispatched_tool_calls','infrastructure_hold','outcome','backend_sha256','cleanup_confirmed')
    for record in raw['rows']:
        row={k:record.get(k) for k in keys}
        row['observed_models']=sorted({r['response'].get('model') for r in record.get('responses',[]) if r['response'].get('model')})
        row['system_fingerprints']=sorted({r['response'].get('system_fingerprint') for r in record.get('responses',[]) if r['response'].get('system_fingerprint')})
        rows.append(row)
    arms={}
    for arm in ('T','V3','V4'):
        selected=[r for r in rows if r['arm']==arm]
        complete=[r['reported_usage'] for r in selected if r['usage_complete']]
        arms[arm]={'scheduled':4,'observed':len(selected),'valid':sum(bool(r['valid']) for r in selected),
            'correct':sum(r['correct'] is True for r in selected),'complete_usage_slots':len(complete),
            'observed_complete_usage_sum':totals(complete),
            'submitted_chat_requests':sum(r['submitted_chat_requests'] or 0 for r in selected)}
    comparisons={}
    for control in ('V3','T'):
        pairs=[]
        for task in frozen['tasks']:
            subset={r['arm']:r for r in rows if r['task']==task}
            c,n=subset.get(control),subset.get('V4')
            both=bool(c and n and c['valid'] and n['valid'] and c['correct'] and n['correct'] and c['usage_complete'] and n['usage_complete'])
            pairs.append({'task':task,'both_success_complete_usage':both,
                'control_total':c['reported_usage']['totalTokens'] if c and c.get('reported_usage') else None,
                'V4_total':n['reported_usage']['totalTokens'] if n and n.get('reported_usage') else None,
                'ratio':n['reported_usage']['totalTokens']/c['reported_usage']['totalTokens'] if both else None})
        ratios=[p['ratio'] for p in pairs if p['ratio'] is not None]
        median=statistics.median(ratios) if ratios else None
        if raw['status']!='COMPLETED' or len(rows)!=12 or not all(r['valid'] for r in rows):disposition='INCONCLUSIVE_INFRASTRUCTURE'
        elif len(ratios)<frozen['screens']['minimum_both_success_pairs']:disposition='INCONCLUSIVE_INSUFFICIENT_PAIRED_SUCCESSES'
        elif arms['V4']['correct']>=arms[control]['correct'] and median<=frozen['screens']['V4_over_'+control+'_max_median_reported_total']:
            disposition='EXPLORATORY_COST_ACCEPTANCE_PASS'
        else:disposition='NO_EXPLORATORY_COST_ADVANTAGE'
        comparisons[control]={'disposition':disposition,'both_success_pairs':len(ratios),
            'median_V4_over_control_total_tokens':median,'pairs':pairs}
    return {'status':raw['status'],'model':frozen['model'],'effort':'low','freeze_sha256':sha((HERE/'FREEZE.json').read_bytes()),
        'model_sessions_started':sum(r['model_sessions_started'] or 0 for r in rows),
        'submitted_chat_requests':raw['submitted_chat_requests'],'input_token_api_calls':0,
        'provider_generation_requests':None,'dollar_cost':None,'arms':arms,'comparisons':comparisons,'rows':rows,
        'limits':['Four first-model-use requirements on two components, partly previously visible code; author-informed, no statistical or competitor superiority claim.',
                  'T is the matched source-proposal Host using the same protected Native publication pipeline.',
                  'All attempts/resources retained; paired cost statistics are success-conditioned.',
                  'Cached input remains in reported total. Missing reasoning breakdown remains null.',
                  'Provider aliases/fingerprints do not establish immutable weights.']}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();result=analyze(a.directory);save(a.output,result)
    print(json.dumps(result['comparisons']))
