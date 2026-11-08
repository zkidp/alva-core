"""Register first-model-use requirements; no model calls or result selection."""
import copy,json,re,subprocess
from pathlib import Path
from benchmarks.context_v4 import assertions
from benchmarks.p37_maintenance_qualification import assertions as old_assertions
from integrations.benchmark_runtime_v2.freeze import pack_git,canonical,sha,decode

ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent


def register():
    registry=json.loads((ROOT/'benchmarks/p37_maintenance_qualification/CANDIDATE-REGISTRY.json').read_bytes())
    bundles=json.loads((ROOT/'benchmarks/p37_maintenance_qualification/TASK-BUNDLES.json').read_bytes())
    tasks={}
    for ident,oldid in [('H01','MM05'),('H02','MM06')]:
        c=next(c for c in registry['candidates'] if c['id']==oldid)
        tasks[ident]={'public_task':{'id':ident,'target':c['target'],'requirement':c['requirement']},
            'bundle':bundles[oldid],'crate':c['crate'],'policy':c['guard_policy'],
            'assertions':{'goal':old_assertions.goals(oldid),'regression':old_assertions.regressions(oldid)},
            'provenance':{'previous_engineering_task':oldid,'previous_model_target':False,'component_previously_visible':True}}
    base=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    bundle=pack_git(ROOT,base,['alva/examples/store_metadata.alva','benchmarks/context_v4/component-metadata.toml'])
    for entry in bundle['payload']['entries']:
        entry['path']='src/metadata.alva' if entry['path'].endswith('.alva') else 'alva.toml'
    bundle['payload_sha256']=sha(canonical(bundle['payload']))
    source=decode(bundle,bundle['payload_sha256'])['src/metadata.alva'].decode()
    functions=re.findall(r'^  \(fn ([a-z_]+)',source,re.M)
    types=re.findall(r'^  \(type ([A-Za-z_]+)',source,re.M)
    specs=[('H03','get_object','Return Err(nil) for an ObjectState.archived object, even if its key exists. Preserve active-object retrieval with all metadata, missing-key errors, storage/list/count operations, enum labels and other declarations. Only get_object body may change.'),
        ('H04','list_objects_page','For every nonnegative i64 offset and limit, return a slice in the existing key enumeration order, clamped to available keys without integer overflow or panic, including i64::MAX. The order must agree with list_objects for the same bucket value; do not introduce sorting or assume lexicographic/insertion order across separately constructed buckets. Preserve ordinary pagination and every non-target function, including archived-object lookup. Keep existing contracts and change only list_objects_page body.')]
    for ident,target,requirement in specs:
        qualified='store.metadata.'+target
        tasks[ident]={'public_task':{'id':ident,'target':qualified,'requirement':requirement},'bundle':copy.deepcopy(bundle),
            'crate':'metadata_holdout','policy':{'authorized_functions':[qualified],
                'modules':{'store.metadata':{'functions':functions,'types':types}}},
            'assertions':{'goal':assertions.goals(ident),'regression':assertions.regressions(ident)},
            'provenance':{'source_commit':base,'source_path':'alva/examples/store_metadata.alva',
                'source_program_unchanged':True,'adaptation':'new component manifest and source path only',
                'previous_model_target':False,'component_previously_visible':False}}
    for task in tasks.values():
        files=decode(task['bundle'],task['bundle']['payload_sha256']);task['input_paths']=list(files)
        local=task['public_task']['target'].rsplit('.',1)[1]
        for path,data in files.items():
            if path.endswith('.alva'):
                lines=data.decode().splitlines()
                hits=[n+1 for n,line in enumerate(lines) if line.strip()=='(fn '+local]
                if len(hits)==1:task['public_task']['source_location']={'path':path,'start':hits[0]}
    result={'schema':'context-v4-task-registration/v3','selected_before_model_use':True,
        'supersedes_rejected':['TASKS-REJECTED-v1.json','TASKS-REJECTED-v2.json'],
        'pre_model_correction':'Compiler implementation uses HashMap and keys().cloned().collect(); preserve enumeration of the same bucket value without presuming global lexicographic or insertion order. Initial erroneous specifications retained. No model slot started.',
        'authorship':'Codex authored/qualified, not independent human holdout',
        'limits':'Four new maintenance targets; two components. H01/H02 component previously visible. No universal or independent-generalization claim.',
        'tasks':tasks,'model_generation_calls':0}
    target=HERE/'TASKS.json'
    if target.exists():raise RuntimeError('TASK_REGISTRATION_IS_IMMUTABLE')
    target.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':register()
