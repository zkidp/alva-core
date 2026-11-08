"""Compile documented forms and exercise actual Core/Guard context workflow."""
import argparse
from pathlib import Path
import subprocess,sys,tempfile
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from integrations.codex.maintenance_context import ContextHost
from integrations.codex.maintenance_host import AgentProcess,MaintenanceHost,project_source_loader
from tests.mcp.host_workflow_test import fixture,ReceiptEvaluator

GRAMMAR='''(module (name "grammar") (version "1.0.0")
 (type Flag (enum (variant enabled) (variant disabled)))
 (type Item (record (field value (prim i64)) (field label (prim string))))
 (fn values (params) (returns (prim i64)) (pure)
  (body (let count (prim i64) (int 2) (+ (ref count) (int 1)))))
 (fn sequence (params) (returns (prim i64)) (pure)
  (body (fold i (range (int 0) (int 3)) (acc total (prim i64) (int 0)) (+ (ref total) (ref i)))))
 (fn record_value (params (param item Item)) (returns Item) (pure)
  (body (record-update Item (ref item) (value (int 3)))))
 (fn choose (params (param flag Flag)) (returns (result (prim i64) (prim string))) (pure)
  (body (match Flag (ref flag) (case enabled (ok (int 1))) (case disabled (err (string "disabled"))))))
 (fn strings (params (param text (prim string))) (returns (prim string)) (pure)
  (body (join (split (ref text) (string ",")) (string ":"))))
 (fn pass (params (param x (result (prim i64) (prim string)))) (returns (result (prim i64) (prim string))) (pure) (body (ref x)))
 (fn retain (params (param x (result (prim i64) (prim string)))) (returns (result (prim i64) (prim string))) (pure)
  (body (let saved (ref x) (ref saved))))
 (fn shadow (params (param x (result (prim i64) (prim string)))) (returns (result (prim i64) (prim string))) (pure)
  (body (let x (prim i64) (int 3) (ref x))))
 (test result_flow (body
  (and (is-ok (call pass (ok (int 2))))
   (and (is-ok (call retain (ok (int 2))))
    (and (== (unwrap (call shadow (err (string "x")))) (int 3))
     (and (is-ok (call choose (variant Flag enabled)))
      (not (is-ok (call choose (variant Flag disabled)))))))))))'''


def main(binary):
    with tempfile.TemporaryDirectory(prefix='context-grammar-') as directory:
        path=Path(directory)/'grammar.alva';path.write_text(GRAMMAR,encoding='utf-8')
        result=subprocess.run([str(binary),'check',str(path),'--json'],capture_output=True,text=True)
        assert result.returncode==0,(result.stdout,result.stderr)
        built=subprocess.run([str(binary),'build',str(path),'--test'],cwd=directory,capture_output=True,text=True)
        assert built.returncode==0,(built.stdout,built.stderr)
        manifest=Path(directory)/'alva.toml'
        manifest.write_text('[project]\nname="grammar"\n[modules]\ngrammar="grammar.alva"\n',encoding='utf-8')
        native=AgentProcess(binary)
        try:
            tx=native.request('tools/call',{'name':'begin_transaction','arguments':{'project':str(manifest)}})['structuredContent']['transaction_id']
            exported=native.request('tools/call',{'name':'export_transaction','arguments':{'transaction_id':tx}})['structuredContent']
            native.request('tools/call',{'name':'abort_transaction','arguments':{'transaction_id':tx}})
        finally:native.close()
        authority=Path(directory)/'alva-air';authority.mkdir()
        (authority/'gen-1.air').write_bytes(bytes.fromhex(exported['air_hex']))
        (authority/'current').write_text('1\n'+exported['project_revision']+'\n',encoding='utf-8')
        output=Path(directory)/'generated'
        built=subprocess.run([str(binary),'project','build',str(manifest),'--out-dir',str(output)],cwd=directory,capture_output=True,text=True)
        assert built.returncode==0,(built.stdout,built.stderr)
        tests=subprocess.run(['cargo','test','--offline','--manifest-path',str(output/'grammar/Cargo.toml')],cwd=directory,capture_output=True,text=True)
        assert tests.returncode==0,(tests.stdout,tests.stderr)
    with tempfile.TemporaryDirectory(prefix='context-host-') as directory:
        root=Path(directory);policy=fixture(root)
        base=MaintenanceHost(lambda:AgentProcess(binary),root/'alva.toml',policy,
            project_source_loader(root/'alva.toml',['alva.toml','m.alva']),ReceiptEvaluator())
        host=ContextHost(base)
        try:
            assert host.invoke('read_reference',{'document':'language','section':'results'})['status']=='REFERENCE'
            assert host.invoke('read_source',{'path':'m.alva'})['status']=='SOURCE'
            assert not (root/'alva-air/current').exists()
            view=host.invoke('read_target',{'function':'m.a'})
            assert '(body' in view['body_syntax']
            proposal=host.invoke('prepare_change',{'view_id':view['view_id'],'body':'(body (int 2))'})
            assert proposal['status']=='PREPARED',proposal
            published=host.invoke('publish_change',{'proposal_id':proposal['proposal_id']})
            assert published['status']=='PUBLISHED' and published['fresh_authority_matches'],published
            assert published['commit']['host_scope']['changed_functions']==['m.a']
            assert host.invoke('read_source',{'path':'alva-air/current'})['status']=='REJECTED'
        finally:host.close()
    print('PASS: documented grammar, read-only context, actual Guard commit and fresh AIR; evaluator receipt stub explicit')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('binary',type=Path);main(p.parse_args().binary.resolve())
