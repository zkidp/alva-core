import copy,json
from pathlib import Path
from integrations.codex.maintenance_context import TOOLS,References
from benchmarks.host_v3_acceptance.protocol import tools as old_tools,INSTRUCTIONS as COMMON,PARAMETERS,LIMITS

ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
ORDERS=(('T','V3','V4'),('V4','V3','T'),('V3','T','V4'),('V4','T','V3'))


def tools(arm):
    result=copy.deepcopy(TOOLS)
    if arm=='T':result[1]=old_tools('T')[1]
    return result


def design():
    tasks=json.loads((HERE/'TASKS.json').read_bytes())['tasks'];ref=References()
    instructions=COMMON.replace('V2/V3','V3/V4').replace(' and study_doc',' and the shared read_reference/read_source context tools').replace('The initial user input contains the original public source-only project and requirement.', 'The initial input identifies the original source-only component and requirement; full source is accessible with read_source.')
    instructions+='''\nUse only the five advertised tools. General Native/CLI transaction tutorials are optional for this Host.
V3 receives the full original source and general Skill up front. V4 and T use the compact official Host Skill and source on demand.
All three have identical access to the same complete public source and full/sectioned references. These are context-loading configurations, not hidden-information conditions.
read_source shows import source in Native conditions; in T it shows the acknowledged source-proposal draft. The read_target body is current semantic authority.
Only prepare_change and publish_change mutate or publish. Read-only tools need no transaction management.
'''
    return {'schema':'context-v4-model-acceptance/v1','model':'deepseek-flash','api_parameters':PARAMETERS,'limits':LIMITS,
        'tasks':tasks,'docs':{'SKILL.md':ref.docs['legacy_skill'],'host_skill':ref.docs['host'],**ref.docs},
        'developer_instructions':instructions,
        'provider_tools':{a:[{'type':'function','function':{'name':t['name'],'description':t['description'],'parameters':t['inputSchema']}} for t in tools(a)] for a in ('T','V3','V4')},
        'schedule':[{'id':f'{task}-{arm}','task':task,'arm':arm} for task,order in zip(tasks,ORDERS) for arm in order],
        'screens':{'minimum_both_success_pairs':3,'candidate_correct_at_least_control':True,
            'V4_over_V3_max_median_reported_total':0.90,'V4_over_T_max_median_reported_total':0.75},
        'boundaries':['First model use of four requirements, two components; author-informed, not independent holdout.',
            'H01/H02 reuse a previously visible component. H03/H04 share a previously untested component.',
            'V3 is full upfront context; V4 is compact/on-demand context; T is matched compact source-proposal Host.',
            'Same accessible public information, actual Guard/tests/publication; no token-count API calls or retries.']}
