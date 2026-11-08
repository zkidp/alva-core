"""Bind independent new protocol/runtime/SDK after zero-model qualification."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

from benchmarks.compact_deepseek.api import API
from benchmarks.context_v4.protocol import ROOT,HERE,design
from benchmarks.context_v4.runner import Remote,Slot,save
from integrations.codex.maintenance_host import sha,canonical

TREE_CODE='''import hashlib,json,pathlib,sys
out={}
for name,value in json.load(sys.stdin).items():
 root=pathlib.Path(value);rows=[]
 for p in sorted(root.rglob('*')):
  if p.is_file():rows.append((p.relative_to(root).as_posix(),hashlib.sha256(p.read_bytes()).hexdigest()))
 out[name]={'files':len(rows),'sha256':hashlib.sha256(json.dumps(rows,separators=(',',':')).encode()).hexdigest()}
print(json.dumps(out))'''


def main(args,remote):
    target=HERE/'FREEZE.json'
    if target.exists():raise RuntimeError('IMMUTABLE_FREEZE_ALREADY_EXISTS')
    pre=json.loads(args.preflight.read_bytes())
    assert pre['status']=='PASS' and len(pre['rows'])==12 and pre['model_generation_calls']==0
    assert pre['production_context_test']=='PASS'
    assert all(r['status']=='PASS' and r['cleanup_confirmed'] for r in pre['rows'])
    metadata=API(args.credentials).request('/models')
    selected=next(m for m in metadata['data'] if m['id']=='deepseek-flash')
    assert 'low' in selected['effort']['supported_levels']
    frozen=design();frozen.update(status='FROZEN_BEFORE_GENERATION',model_metadata=selected,
        metadata_sha256=sha(canonical(metadata)),preflight_sha256=sha(args.preflight.read_bytes()),
        registration_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        controller_python_sha256=sha(Path(sys.executable).read_bytes()))
    files=set(subprocess.check_output(['git','ls-files','*.py'],cwd=ROOT,text=True).splitlines())
    files.update(p.relative_to(ROOT).as_posix() for p in HERE.glob('*.py'))
    frozen['local_runtime_files']={p:sha((ROOT/p).read_bytes()) for p in sorted(files)}
    frozen['remote_runtime_files']=remote.identities(sorted(files))
    sdk=remote.cfg['sdk'];observed=remote.identities([sdk['alva'],sdk['toolchain']+'/bin/rustc'])
    frozen['sdk_executables']={'alva':observed[sdk['alva']],'rustc':observed[sdk['toolchain']+'/bin/rustc']}
    frozen['sdk_trees']=remote.checked(['python3','-c',TREE_CODE],{k:sdk[k] for k in ('toolchain','registry')},timeout=180)
    frozen['transport_preflight']=[]
    for arm in ('T','V3','V4'):
        entry={'task':'H01','arm':arm}
        slot=Slot(remote,entry,frozen)
        ready=slot.tool('read_target',{'function':frozen['tasks']['H01']['public_task']['target']})
        assert ready['structuredContent']['status']=='READY'
        result=slot.finish()
        assert not result['correct'] and result['task']=='TEST_FAIL' and result['regression']=='PASS' and result['cleanup_confirmed']
        frozen['transport_preflight'].append({'arm':arm,'status':'PASS','model_generation_calls':0,'cleanup_confirmed':True})
    frozen['byte_boundary']='Separate exact controller/export maps; Linux shebang normalization is explicitly bound, not assumed byte equivalence.'
    save(HERE/'PREFLIGHT.json',pre);save(target,frozen)
    print(json.dumps({'status':frozen['status'],'slots':12,'model':selected['id'],
        'runtime_files':len(files),'freeze_sha256':sha(target.read_bytes()),'model_generation_calls':0}))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for k in ('connection','credentials','preflight'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();remote=Remote(a.connection)
    try:main(a,remote)
    finally:remote.close()
