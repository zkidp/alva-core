"""Trusted Linux Host adapter. No API key/model runs; candidates execute only in P22.

This checkout and evaluators are never mounted in candidate namespaces.
"""
import argparse
import copy
import json
from pathlib import Path
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from benchmarks.host_v3_acceptance.protocol import design,tools
from benchmarks.maintenance_interface_comparison.service import evaluate
from integrations.benchmark_runtime_v2.freeze import decode
from integrations.benchmark_runtime_v2.sandbox import SDK
from integrations.codex.maintenance_evaluator import LinuxProjectEvaluator
from integrations.codex.maintenance_host import AgentProcess,MaintenanceHost,PRIVATE_OPERATIONS,ToolFailure,project_source_loader,sha,tool_result
from integrations.codex.precommit_scope_guard import GuardedNative


def sources(root,files):
    for name,data in files.items():
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)


def snapshot(binary,manifest,policy,baseline=None,body_target=None,*,ledger=None,origin='neutral'):
    start=time.monotonic()
    native=AgentProcess(binary)
    guard=GuardedNative(native,policy,PRIVATE_OPERATIONS,snapshot_tool='inspect_scope_snapshot')
    def call(name,**args):
        value=guard.tool(name,args)
        if value.get('isError'):raise ToolFailure(value)
        return value['structuredContent']
    try:
        tx=call('begin_transaction',project=str(manifest))['transaction_id']
        observed=copy.deepcopy(guard._baselines[tx])
        if 'error' in observed:raise RuntimeError('INCOMPLETE_NEUTRAL_SNAPSHOT')
        if baseline is not None:guard._baselines[tx]=copy.deepcopy(baseline)
        decision=guard.preview_scope(tx)
        info=None
        if body_target and decision['status']=='SCOPE_ALLOWED':
            checked=call('check_transaction',transaction_id=tx)
            if checked.get('problems'):raise RuntimeError('SOURCE_CHECK_FAILED')
            info=call('read_function',transaction_id=tx,function=body_target)
        call('abort_transaction',transaction_id=tx)
        return observed,decision,info
    finally:
        try:native.close()
        finally:
            if ledger is not None:ledger.append({'origin':origin,'native_calls':native.seq,
                'native_wire_bytes':dict(native.transport_stats),'seconds':time.monotonic()-start})


class RecordingEvaluator(LinuxProjectEvaluator):
    def __init__(self,*a,**kw):super().__init__(*a,**kw);self.receipts=[]
    def __call__(self,*a):
        value=super().__call__(*a);self.receipts.append(value);return value


class Session:
    def __init__(self,task,arm,sdk):
        self.task,self.arm,self.sdk=task,arm,sdk
        self.tmp=tempfile.TemporaryDirectory(prefix='host-acceptance-')
        self.root=Path(self.tmp.name)
        self.original=decode(task['bundle'],task['bundle']['payload_sha256'])
        self.text=copy.deepcopy(self.original)
        sources(self.root,self.original)
        self.auxiliary_native_work=[]
        self.baseline,_,_=snapshot(sdk.alva,self.root/'alva.toml',task['policy'],ledger=self.auxiliary_native_work,origin='setup')
        self.evaluator=RecordingEvaluator(sdk,task['crate'],assertions='\n'.join(task['assertions'].values()))
        self.host=MaintenanceHost(lambda:AgentProcess(sdk.alva),self.root/'alva.toml',task['policy'],
            project_source_loader(self.root/'alva.toml',task['input_paths']),self.evaluator,
            bulk_scope=arm!='V2',digest_rechecks=arm!='V2')
        self.published=[];self.calls=[];self.closed=False

    def text_prepare(self,args):
        self.host.proposal=None
        if not isinstance(args,dict) or set(args)!={'view_id','edits'} or not self.host.view or args['view_id']!=self.host.view['id']:
            return {'status':'REJECTED','reason':'INVALID_TEXT_VIEW_OR_ARGUMENTS','source_edits_applied':False}
        edits=args['edits'];changed=copy.deepcopy(self.text)
        if not isinstance(edits,list) or not 1<=len(edits)<=8:
            return {'status':'REJECTED','reason':'EDITS_BOUND','source_edits_applied':False}
        for edit in edits:
            if not isinstance(edit,dict) or set(edit)!={'path','old','new'} or any(not isinstance(v,str) for v in edit.values()):
                return {'status':'REJECTED','reason':'INVALID_EDIT','source_edits_applied':False}
            path,old,new=edit['path'],edit['old'],edit['new']
            if path not in changed or path=='alva.toml' or not old or len(new.encode())>65536:
                return {'status':'REJECTED','reason':'PROTECTED_PATH_OR_EDIT_BOUND','source_edits_applied':False}
            text=changed[path].decode()
            if text.count(old)!=1:
                return {'status':'REJECTED','reason':'OLD_SPAN_MUST_MATCH_EXACTLY_ONCE','source_edits_applied':False}
            changed[path]=text.replace(old,new,1).encode()
        if changed==self.text:return {'status':'UNCHANGED','source_edits_applied':False,'can_publish':False}
        with tempfile.TemporaryDirectory(prefix='source-proposal-') as directory:
            root=Path(directory);sources(root,changed)
            try:
                _,decision,info=snapshot(self.sdk.alva,root/'alva.toml',self.task['policy'],self.baseline,
                    self.task['public_task']['target'],ledger=self.auxiliary_native_work,origin='text_source_import')
            except ToolFailure as e:
                return {'status':'REJECTED','reason':str(e)[:2400],'source_edits_applied':False}
            if decision['status']!='SCOPE_ALLOWED' or decision['changed_functions']!=[self.task['public_task']['target']]:
                return {'status':decision['status'] if decision['status']!='SCOPE_ALLOWED' else 'REJECTED',
                    'reason':'SOURCE_PROPOSAL_SCOPE_REJECTED','source_edits_applied':False}
        value=self.host.invoke('prepare_change',{'view_id':args['view_id'],'body':info['body']})
        applied=value['status'] in ('PREPARED','VALIDATION_FAILED','UNVERIFIED_TEST_RECEIPT','DRAFT_CHANGED_DURING_EVALUATION')
        if applied:self.text=changed
        return dict(value,source_edits_applied=applied)

    def tool(self,name,args):
        if name=='study_doc':
            docs=design()['docs']
            value={'content':docs[args['path']]} if isinstance(args,dict) and set(args)=={'path'} and isinstance(args['path'],str) and args['path'] in docs else {'error':'PUBLIC_DOCUMENT_NOT_FOUND'}
        elif name not in {t['name'] for t in tools(self.arm)}:
            value={'status':'REJECTED','reason':'TOOL_NOT_EXPOSED'}
        elif self.arm=='T' and name=='prepare_change':value=self.text_prepare(args)
        else:value=self.host.invoke(name,args)
        self.calls.append({'name':name,'arguments':args,'trusted_result':value})
        if value.get('status') in ('PUBLISHED','PUBLISHED_UNVERIFIED'):self.published.append(value)
        if name=='study_doc':return value
        public=copy.deepcopy(value)
        if self.arm=='V2' and 'host_work' in public:
            for k in ('native_seconds','native_wire_request_bytes','native_wire_reply_bytes'):public['host_work'].pop(k,None)
        return tool_result(public,compact=self.arm!='V2')

    def finish(self):
        self.host.close()
        files={p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        final=evaluate(files,self.sdk,self.task)
        observed,scope,_=snapshot(self.sdk.alva,self.root/'alva.toml',self.task['policy'],self.baseline,
            ledger=self.auxiliary_native_work,origin='final_fresh_scope')
        commit=self.published[-1] if self.published else None
        fresh=bool(commit and commit.get('status')=='PUBLISHED' and commit['commit']['revision']==observed['project_revision'])
        correct=bool(final['goal']['status']==final['regression']['status']=='PASS' and
            scope['status']=='SCOPE_ALLOWED' and scope['changed_functions']==[self.task['public_task']['target']] and fresh)
        result={'correct':correct,'task':final['goal']['status'],'regression':final['regression']['status'],
            'scope':scope,'fresh_authority_matches':fresh,'successful_publications':len(self.published),
            'host_work':self.host.work,'tested_snapshot_sha256':final['tested_snapshot_sha256'],
            'original_sources_unchanged':all((self.root/p).read_bytes()==b for p,b in self.original.items()),
            'backend_evaluation_runs':len(self.evaluator.receipts),
            'draft_evaluation_work':[r.get('work') for r in self.evaluator.receipts],
            'auxiliary_native_work':self.auxiliary_native_work,
            'independent_final_commands':sum(k in final[suite] for suite in ('goal','regression') for k in ('check','build','tests')),
            'calls':self.calls,'evaluations':self.evaluator.receipts}
        self.tmp.cleanup();self.closed=True
        result['cleanup_confirmed']=not self.root.exists()
        return result

    def close(self):
        if not self.closed:
            try:self.host.close()
            finally:self.tmp.cleanup();self.closed=True


def serve(args):
    from benchmarks.maintenance_interface_comparison.linux_profile import install
    install()
    sdk=SDK(*(Path(getattr(args,k)).resolve() for k in ('alva','toolchain','registry')))
    task=design()['tasks'][args.task]
    session=Session(task,args.arm,sdk)
    print(json.dumps({'ready':True,'tools':tools(args.arm),'alva_sha256':sha(sdk.alva.read_bytes())}),flush=True)
    try:
        for line in sys.stdin:
            req=json.loads(line)
            if req['action']=='finish':
                result=session.finish();print(json.dumps(result),flush=True);break
            if req['action']!='tool':raise RuntimeError('UNSUPPORTED_TRUSTED_ACTION')
            print(json.dumps(session.tool(req['name'],req['arguments'])),flush=True)
    finally:session.close()


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for k in ('task','arm','alva','toolchain','registry'):p.add_argument('--'+k,required=True)
    serve(p.parse_args())
