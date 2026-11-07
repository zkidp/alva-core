"""Fresh prospective acceptance; no generation or historical solution imports."""
import copy
import json
from pathlib import Path

from integrations.codex.maintenance_host import TOOLS

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).parent
ARMS=('T','V2','V3')
ORDERS=(('T','V2','V3'),('V3','V2','T'),('V2','T','V3'),('V3','T','V2'))
PARAMETERS={'thinking':{'type':'enabled'},'reasoning_effort':'low','max_tokens':8192,'stream':False}
LIMITS={'tool_callback_limit':80,'wall_observation_seconds':480,'token_observation_threshold':600000,
        'interrupt_grace_seconds':20,'max_slots':12,'model_turns_per_slot':1,'concurrency':1}


def documents():
    # Retain the public language reference already used in the registered
    # source-only tasks; official Skill/reference bytes are current and equal.
    registration=json.loads((ROOT/'benchmarks/compact_maintenance/REGISTRATION.json').read_bytes())
    docs={'language.md':registration['docs']['language.md']}
    for name in ('SKILL.md','references/workflow.md','references/diagnostics.md','references/examples.md'):
        docs[name]=(ROOT/'integrations/skills/alva'/name).read_text(encoding='utf-8')
    return docs


def tools(arm):
    out=copy.deepcopy(TOOLS)
    if arm=='T':
        out[1]={'name':'prepare_change','description':'Prepare unique exact source-span edits at view_id. Host checks imported scope and tests the isolated draft. Does not publish. Failed preparation invalidates older proposals. source_edits_applied tells whether draft text changed.',
          'inputSchema':{'type':'object','properties':{'view_id':{'type':'string','minLength':1},
          'edits':{'type':'array','minItems':1,'maxItems':8,'items':{'type':'object','properties':{
          'path':{'type':'string'},'old':{'type':'string','minLength':1},'new':{'type':'string'}},
          'required':['path','old','new'],'additionalProperties':False}}},'required':['view_id','edits'],'additionalProperties':False}}
    out.append({'name':'study_doc','description':'Read a shared public language or official Skill reference. No hidden tests or edit solutions.',
        'inputSchema':{'type':'object','properties':{'path':{'type':'string','enum':list(documents())}},'required':['path'],'additionalProperties':False}})
    return out


INSTRUCTIONS='''Maintain the original ALVA component under its public task. Only the authorized target function body may change.
The initial user input contains the original public source-only project and requirement. Hidden evaluators, historical solutions and runs are unavailable.
Use read_target, prepare_change, publish_change and study_doc only. No shell, arbitrary file access, test changes or operator recovery.
Read target, prepare a candidate, review diff/checks, publish its passing proposal. A staged draft is not a publication.
Host owns transactions, revision handling, actual scope authorization, isolated check/build/test and fresh AIR verification.
An error can be repaired within this one conversation and fixed budget. Read again after expiry/conflict. Never replay a consumed proposal.
The official Skill and references are public context; these condition-specific instructions override incompatible tool-call examples:
V2/V3 submit a complete ALVA (body ...) fragment to prepare_change. T submits unique exact old/new source spans at public source paths.
T source edits are atomic on syntax/scope rejection; source_edits_applied reports whether a type-valid tested draft was retained. Track accepted edits; initial sources are the original snapshot.
T's Host imports source through the real compiler, checks actual P34 scope against the original component, and attaches the target body to the same protected Native publication pipeline. T is a source-proposal control, not a different language or unrestricted text agent.
Tool feedback supplies check/build/test status, not hidden assertions. Do not claim task success without PUBLISHED and fresh authority verification.
One initial user message; max 80 tool observations, 480 active seconds, 600000 cumulative provider-reported tokens observation, concurrency one.
Successful publication ends the slot immediately for every condition; otherwise a normal final response or a limit ends it. No replacement or additional user turn.
'''


def design():
    old=json.loads((ROOT/'benchmarks/compact_maintenance/REGISTRATION.json').read_bytes())
    ids=('MM01','MM02','MM04','MM07')
    return {'schema':'host-v3-model-acceptance/v1','model':'deepseek-flash','api_parameters':PARAMETERS,
        'limits':LIMITS,'tasks':{k:old['tasks'][k] for k in ids},'docs':documents(),
        'developer_instructions':INSTRUCTIONS,'provider_tools':{a:[{'type':'function','function':{
            'name':t['name'],'description':t['description'],'parameters':t['inputSchema']}} for t in tools(a)] for a in ARMS},
        'schedule':[{'id':f'{task}-{arm}','task':task,'arm':arm} for task,order in zip(ids,ORDERS) for arm in order],
        'screens':{'minimum_both_success_pairs':3,'candidate_correct_at_least_control':True,
            'V3_over_V2_max_median_reported_total':0.90,'V3_over_T_max_median_reported_total':0.75},
        'boundaries':['known author-informed tasks; one slot per task/arm; no statistical or competitor claim',
            'V2 is the serial/full-export/full-receipt configuration on the same instrumented current compiler',
            'T is a matched source-proposal Host; same public source, docs, P34/tests and Native publication',
            'all attempts retained; no cached subtraction; unknown provider generation requests/dollars remain null',
            'stop entire schedule on provider uncertainty, identity drift, isolation or cleanup failure; no replay']}
