"""Opt-in compact Host profile and bounded public context readers.

All mutation/publication still delegates to MaintenanceHost unchanged. No
task requirements, evaluators, witness material or model API is consulted.
"""
from __future__ import annotations
import copy
import json
from pathlib import Path
import re
import threading

from integrations.codex.maintenance_host import TOOLS as MUTATIONS,MaintenanceHost,AgentProcess,project_source_loader,sha,tool_result

ROOT=Path(__file__).resolve().parents[2]
PROFILE=ROOT/'integrations/skills/alva-host'


def sectioned(text):
    result={};name='overview';lines=[];fenced=False
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith('```'):fenced=not fenced
        if not fenced and line.startswith('## '):
            if lines:result[name]=''.join(lines)
            title=line[3:].strip();base=re.sub('[^a-z0-9]+','-',title.lower()).strip('-') or 'section'
            name=base;number=2
            while name in result:name=base+'-'+str(number);number+=1
            lines=[]
        lines.append(line)
    if lines:result[name]=''.join(lines)
    return result


class References:
    def __init__(self):
        general=ROOT/'integrations/skills/alva'
        self.docs={'host':(PROFILE/'SKILL.md').read_text(encoding='utf-8'),
            'language':(PROFILE/'references/language.md').read_text(encoding='utf-8'),
            'legacy_skill':(general/'SKILL.md').read_text(encoding='utf-8'),
            **{n:(general/'references'/f'{n}.md').read_text(encoding='utf-8') for n in ('workflow','diagnostics','examples')},
            'legacy_language':(ROOT/'alva/README.md').read_text(encoding='utf-8')}
        self.sections={name:sectioned(text) for name,text in self.docs.items()}
    def read(self,args):
        if not isinstance(args,dict) or set(args)!={'document','section'} or any(not isinstance(x,str) for x in args.values()):
            return {'status':'REJECTED','reason':'INVALID_REFERENCE_ARGUMENTS'}
        name,key=args['document'],args['section']
        if name not in self.docs:return {'status':'REJECTED','reason':'UNKNOWN_PUBLIC_DOCUMENT'}
        if key=='index':return {'status':'REFERENCE','document':name,'sections':list(self.sections[name]),'whole_document':'all'}
        text=self.docs[name] if key=='all' else self.sections[name].get(key)
        if text is None:return {'status':'REJECTED','reason':'UNKNOWN_SECTION','sections':list(self.sections[name])}
        return {'status':'REFERENCE','document':name,'section':key,'content':text,'sha256':sha(text.encode())}


READ_TOOLS=[
    {'name':'read_reference','description':'Read a shared public reference by section, or index/all. Host language sections: body, bindings, collections, records, results, strings, diagnostics. General Native tutorials are optional for this Host profile.',
     'inputSchema':{'type':'object','properties':{'document':{'type':'string','enum':['host','language','legacy_skill','workflow','diagnostics','examples','legacy_language']},
        'section':{'type':'string','minLength':1}},'required':['document','section'],'additionalProperties':False}},
    {'name':'read_source','description':'Read public source lines only when needed. Import source is not staged AIR. Returns exact text and next_start; cannot read AIR, tests/evaluators outside the supplied source bundle, or arbitrary files.',
     'inputSchema':{'type':'object','properties':{'path':{'type':'string','minLength':1},'start':{'type':'integer','minimum':1},
        'count':{'type':'integer','minimum':1,'maximum':120}},'required':['path'],'additionalProperties':False}}]
TOOLS=copy.deepcopy(MUTATIONS)+READ_TOOLS


def source_read(files,args,authority='IMPORT_SOURCE_NOT_STAGED_AIR'):
    if not isinstance(args,dict) or set(args)-{'path','start','count'} or not isinstance(args.get('path'),str):
        return {'status':'REJECTED','reason':'INVALID_SOURCE_ARGUMENTS'}
    start,count=args.get('start',1),args.get('count',80)
    if type(start) is not int or type(count) is not int or start<1 or not 1<=count<=120:
        return {'status':'REJECTED','reason':'SOURCE_LINE_BOUND'}
    path=args['path']
    if path not in files:return {'status':'REJECTED','reason':'NOT_A_PUBLIC_SOURCE_PATH'}
    try:lines=files[path].decode('utf-8').splitlines(keepends=True)
    except UnicodeDecodeError:return {'status':'REJECTED','reason':'SOURCE_ENCODING_UNSUPPORTED'}
    selected=[];size=0
    for line in lines[start-1:start-1+count]:
        length=len(line.encode())
        if size+length>16384:break
        selected.append(line);size+=length
    if not selected and start<=len(lines):return {'status':'REJECTED','reason':'SOURCE_LINE_EXCEEDS_BYTE_BOUND'}
    next_start=start+len(selected);eof=next_start>len(lines)
    return {'status':'SOURCE','path':path,'start':start,'content':''.join(selected),
        'source_sha256':sha(files[path]),'authority':authority,'eof':eof,'next_start':None if eof else next_start}


class ContextHost:
    def __init__(self,host):
        self.host=host;self.references=References();self.lock=threading.RLock()
        self.work={'reference_reads':0,'source_reads':0,'context_reply_bytes':0}
    def invoke(self,name,args):
        with self.lock:
            if name=='read_reference':
                result=self.references.read(args);self.work['reference_reads']+=1
            elif name=='read_source':
                result=source_read(self.host._load_sources(),args);self.work['source_reads']+=1
            else:
                result=self.host.invoke(name,args)
                if name=='read_target' and result.get('status')=='READY':
                    result['body_syntax']=self.references.sections['language']['body']
            self.work['context_reply_bytes']+=len(json.dumps(result).encode())
            return result
    def close(self):self.host.close()


def serve(host,incoming,outgoing):
    while line:=incoming.readline(1024**2+1):
        if len(line.encode())>1024**2:raise RuntimeError('HOST_REQUEST_LIMIT')
        try:
            req=json.loads(line)
            if not isinstance(req,dict):raise ValueError()
        except (ValueError,TypeError):
            outgoing.write(json.dumps({'jsonrpc':'2.0','id':None,'error':{'code':-32700,'message':'Parse error'}})+'\n');outgoing.flush();continue
        if 'id' not in req:continue
        method=req.get('method')
        if method=='initialize':value={'protocolVersion':'2025-11-25','capabilities':{'tools':{}},
            'serverInfo':{'name':'alva-context-host','version':'0.2'},'instructions':host.references.docs['host']}
        elif method=='tools/list':value={'tools':TOOLS}
        elif method=='ping':value={}
        elif method=='tools/call':
            params=req.get('params',{});params=params if isinstance(params,dict) else {}
            result=host.invoke(params.get('name'),params.get('arguments'))
            value=tool_result(result)
            if result.get('status') in ('SOURCE','REFERENCE'):value['isError']=False
        else:
            outgoing.write(json.dumps({'jsonrpc':'2.0','id':req['id'],'error':{'code':-32601,'message':'Method not found'}})+'\n');outgoing.flush();continue
        outgoing.write(json.dumps({'jsonrpc':'2.0','id':req['id'],'result':value})+'\n');outgoing.flush()


if __name__=='__main__':
    import argparse,sys
    from integrations.benchmark_runtime_v2.sandbox import SDK
    from integrations.codex.maintenance_evaluator import LinuxProjectEvaluator
    p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);a=p.parse_args()
    config=json.loads(a.config.read_bytes());sdk=SDK(*(Path(config[k]).resolve() for k in ('alva','toolchain','registry')))
    host=ContextHost(MaintenanceHost(lambda:AgentProcess(sdk.alva),config['project'],config['policy'],
        project_source_loader(config['project'],config.get('inputs')),
        LinuxProjectEvaluator(sdk,config['crate'],assertions=config.get('assertions',''))))
    try:serve(host,sys.stdin,sys.stdout)
    finally:host.close()
