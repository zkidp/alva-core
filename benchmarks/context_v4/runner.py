"""Prospective Windows controller. API credentials never leave this process.

Fresh SSH-owned trusted service per slot; no model retries or slot replacement.
Raw provider reasoning/transcripts are private .local artifacts only.
"""
import argparse
import getpass
import json
from pathlib import Path
import queue
import shlex
import subprocess
import sys
import threading
import time

from benchmarks.compact_deepseek.api import API,ProviderFault,totals,usage
from benchmarks.compact_deepseek.runner import bounded_request,model_result
from benchmarks.context_v4.protocol import ROOT,HERE,design
from integrations.codex.maintenance_host import sha,canonical
from integrations.benchmark_runtime_v2.freeze import decode


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,ensure_ascii=True)+'\n',encoding='utf-8')


class Remote:
    def __init__(self,path):
        import paramiko
        self.cfg=json.loads(path.read_bytes())
        self.client=paramiko.SSHClient();self.client.load_host_keys(self.cfg['known_hosts'])
        self.client.set_missing_host_key_policy(paramiko.RejectPolicy())
        self.client.connect(self.cfg['host'],port=self.cfg.get('port',22),username=self.cfg['username'],
            password=getpass.getpass('SSH password: '),allow_agent=False,look_for_keys=False,timeout=15,auth_timeout=15)
    def command(self,argv):
        return 'cd '+shlex.quote(self.cfg['root'])+' && '+' '.join(shlex.quote(str(x)) for x in argv)
    def checked(self,argv,data=None,timeout=120):
        incoming,out,err=self.client.exec_command(self.command(argv),timeout=timeout)
        if data is not None:incoming.write(json.dumps(data));incoming.flush()
        incoming.channel.shutdown_write()
        text=out.read();errors=err.read();status=out.channel.recv_exit_status()
        if status:raise RuntimeError('TRUSTED_REMOTE_COMMAND_FAILED:'+str(status))
        return json.loads(text)
    def identities(self,paths):
        code="import hashlib,json,pathlib,sys;print(json.dumps({p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest() for p in json.load(sys.stdin)}))"
        return self.checked(['python3','-c',code],paths)
    def close(self):self.client.close()


class Slot:
    def __init__(self,remote,entry,frozen):
        self.remote=remote;self.entry=entry
        argv=['python3','-u','-m','benchmarks.context_v4.service','--task',entry['task'],'--arm',entry['arm']]
        for k,v in remote.cfg['sdk'].items():argv+=['--'+k,v]
        self.stdin,self.stdout,self.stderr=remote.client.exec_command(remote.command(argv),timeout=150)
        self.lines=queue.Queue();self.errors=bytearray();self.finished=False
        def read():
            while line:=self.stdout.readline(24*1024**2+1):self.lines.put(line)
            self.lines.put(None)
        def errors():
            while block:=self.stderr.read(4096):
                if isinstance(block,str):block=block.encode()
                if len(self.errors)<65536:self.errors.extend(block)
        self.reader=threading.Thread(target=read,daemon=True);self.err_reader=threading.Thread(target=errors,daemon=True)
        self.reader.start();self.err_reader.start()
        try:
            ready=self.receive()
            expected=[{'type':'function','function':{'name':t['name'],'description':t['description'],'parameters':t['inputSchema']}} for t in ready['tools']]
            if not ready.get('ready') or expected!=frozen['provider_tools'][entry['arm']] or ready['alva_sha256']!=frozen['sdk_executables']['alva']:
                raise RuntimeError('REMOTE_SERVICE_IDENTITY_OR_TOOLS_MISMATCH')
        except Exception:
            self.close();raise
    def receive(self):
        try:line=self.lines.get(timeout=150)
        except queue.Empty:raise RuntimeError('TRUSTED_SERVICE_TIMEOUT_NO_REPLAY') from None
        if not line or len(line)>24*1024**2:raise RuntimeError('TRUSTED_SERVICE_CLOSED_OR_OVERSIZE')
        return json.loads(line)
    def request(self,value):
        self.stdin.write(json.dumps(value)+'\n');self.stdin.flush()
        return self.receive()
    def tool(self,name,args):return self.request({'action':'tool','name':name,'arguments':args})
    def finish(self):
        result=self.request({'action':'finish'});self.finished=True
        self.close()
        return result
    def close(self):
        self.stdin.channel.shutdown_write()
        start=time.monotonic()
        while not self.stdout.channel.exit_status_ready():
            if time.monotonic()-start>20:
                self.stdout.channel.close();raise RuntimeError('REMOTE_CLEANUP_UNCONFIRMED')
            time.sleep(.05)
        code=self.stdout.channel.recv_exit_status()
        self.reader.join(3);self.err_reader.join(3)
        if code or self.reader.is_alive() or self.err_reader.is_alive():raise RuntimeError('REMOTE_CLEANUP_UNCONFIRMED')
        for f in (self.stdin,self.stdout,self.stderr):f.close()


def verify(frozen,remote):
    for p,h in frozen['local_runtime_files'].items():
        if sha((ROOT/p).read_bytes())!=h:raise RuntimeError('LOCAL_RUNTIME_DRIFT:'+p)
    if remote.identities(list(frozen['remote_runtime_files']))!=frozen['remote_runtime_files']:
        raise RuntimeError('REMOTE_RUNTIME_DRIFT')
    sdk=remote.cfg['sdk']
    observed=remote.identities([sdk['alva'],sdk['toolchain']+'/bin/rustc'])
    if {'alva':observed[sdk['alva']],'rustc':observed[sdk['toolchain']+'/bin/rustc']}!=frozen['sdk_executables']:
        raise RuntimeError('SDK_EXECUTABLE_DRIFT')
    if sha(Path(sys.executable).read_bytes())!=frozen['controller_python_sha256']:raise RuntimeError('PYTHON_EXECUTABLE_DRIFT')


def conversation(api,slot,frozen,record):
    entry=slot.entry;task=frozen['tasks'][entry['task']]
    original=decode(task['bundle'],task['bundle']['payload_sha256'])
    # Exact same public source/doc information in all conditions. No hidden
    # evaluator, engineering witness, previous model record or protocol result.
    user={'task':task['public_task'],'source_paths':list(original)}
    if entry['arm']=='V3':user['source_files']={p:b.decode() for p,b in original.items()}
    messages=[{'role':'system','content':frozen['developer_instructions']+'\nCondition: '+entry['arm']+
               '\nActive official profile:\n'+frozen['docs']['SKILL.md' if entry['arm']=='V3' else 'host_skill']},
              {'role':'user','content':json.dumps(user,ensure_ascii=False)}]
    tools=frozen['provider_tools'][entry['arm']];allowed={t['function']['name'] for t in tools}
    record.update(initial_messages=messages.copy(),responses=[],tool_events=[],usage_reports=[],
        submitted_chat_requests=0,observed_tool_calls=0,dispatched_tool_calls=0)
    start=time.monotonic()
    try:
        while True:
            remaining=frozen['limits']['wall_observation_seconds']-(time.monotonic()-start)
            total=totals(record['usage_reports'])['totalTokens']
            if remaining<=0 or (total is not None and total>=frozen['limits']['token_observation_threshold']):
                record['stop_reason']='OBSERVATION_LIMIT_BETWEEN_REQUESTS';return
            payload={'model':frozen['model'],'messages':messages,'tools':tools,**frozen['api_parameters']}
            record['submitted_chat_requests']+=1
            response=bounded_request(api,payload,remaining)
            record['responses'].append({'request_sha256':sha(canonical(payload)),'response':response})
            if response.get('model')!=frozen['model']:raise ProviderFault('REPORTED_MODEL_MISMATCH')
            u=usage(response.get('usage') or {});record['usage_reports'].append(u)
            if type(u['totalTokens']) is not int:raise ProviderFault('MISSING_REPORTED_TOTAL')
            choice=response['choices'][0];message=choice['message'];reason=choice.get('finish_reason')
            if reason not in ('stop','tool_calls','length','content_filter','insufficient_system_resource'):
                raise ProviderFault('UNRECOGNIZED_FINISH_REASON')
            if reason=='insufficient_system_resource':raise ProviderFault('PROVIDER_INSUFFICIENT_SYSTEM_RESOURCE')
            if reason in ('length','content_filter'):record['stop_reason']='MODEL_'+reason.upper();return
            if not message.get('tool_calls'):
                record['stop_reason']='NORMAL_STOP';record['terminal_confirmed']=True;return
            messages.append(message) # Preserve private reasoning_content in tool continuations.
            record['observed_tool_calls']+=len(message['tool_calls'])
            for tool in message['tool_calls']:
                if record['dispatched_tool_calls']>=80 or time.monotonic()-start>=480:
                    record['stop_reason']='TOOL_OR_ACTIVE_OBSERVATION_LIMIT';return
                name=tool['function']['name'];before=time.monotonic()
                try:args=json.loads(tool['function']['arguments'])
                except (ValueError,TypeError):args=None;value={'error':'INVALID_TOOL_ARGUMENTS'}
                else:value=slot.tool(name,args) if name in allowed else {'error':'TOOL_NOT_EXPOSED'}
                record['dispatched_tool_calls']+=1
                normalized=model_result(value)
                record['tool_events'].append({'name':name,'arguments':args,'response':normalized,'seconds':time.monotonic()-before})
                messages.append({'role':'tool','tool_call_id':tool['id'],'content':json.dumps(normalized,ensure_ascii=False)})
                status=normalized.get('structuredContent',normalized).get('status')
                if status in ('BLOCKED','PUBLISHED_UNVERIFIED'):raise RuntimeError('HOST_OUTCOME_REQUIRES_HOLD:'+status)
                if name=='publish_change' and status=='PUBLISHED':
                    record['stop_reason']='PUBLISHED';record['terminal_confirmed']=True;return
    finally:
        record['active_seconds']=time.monotonic()-start
        record['reported_usage']=totals(record['usage_reports'])
        record['usage_complete']=len(record['responses'])==record['submitted_chat_requests'] and all(
            type(record['reported_usage'].get(k)) is int for k in ('totalTokens','inputTokens','cachedInputTokens','outputTokens'))


def run(args,remote):
    frozen=json.loads((HERE/'FREEZE.json').read_bytes());identity=sha((HERE/'FREEZE.json').read_bytes())
    if frozen['status']!='FROZEN_BEFORE_GENERATION':raise RuntimeError('UNQUALIFIED_FREEZE')
    if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT):raise RuntimeError('DIRTY_WORKTREE')
    reservation=ROOT/'.local/context-v4'/('RESERVED-'+identity+'.json')
    reservation.parent.mkdir(parents=True,exist_ok=True)
    with reservation.open('x') as f:json.dump({'freeze_sha256':identity,'max_slots':12},f)
    args.output.mkdir(parents=True,exist_ok=False)
    api=API(args.credentials);rows=[]
    for entry in frozen['schedule']:
        record={**entry,'correct':None,'valid':False,'terminal_confirmed':False,'model_sessions_started':0,
            'provider_generation_requests':None,'dollar_cost':None}
        slot=None;setup_start=time.monotonic();print('START '+entry['id'],flush=True)
        try:
            verify(frozen,remote)
            slot=Slot(remote,entry,frozen)
            record['setup_seconds']=time.monotonic()-setup_start
            record['model_sessions_started']=1
            conversation(api,slot,frozen,record)
        except Exception as exc:record['infrastructure_hold']=type(exc).__name__+':'+str(exc)[:180]
        finally:
            finish_start=time.monotonic()
            if slot:
                try:
                    backend=slot.finish();save(args.output/entry['id']/'backend.json',backend)
                    record['backend_sha256']=sha(canonical(backend))
                    record['outcome']={k:v for k,v in backend.items() if k not in ('calls','evaluations')}
                    record['correct']=bool(backend['correct'] and record['terminal_confirmed'])
                    record['cleanup_confirmed']=backend['cleanup_confirmed']
                except Exception as exc:record['infrastructure_hold']='FINALIZATION:'+type(exc).__name__+':'+str(exc)[:120]
            try:verify(frozen,remote)
            except Exception as exc:record['infrastructure_hold']='POST_IDENTITY:'+type(exc).__name__
            record['valid']=not record.get('infrastructure_hold') and record.get('cleanup_confirmed') is True
            record['finalization_seconds']=time.monotonic()-finish_start
            rows.append(record);save(args.output/entry['id']/'record.json',record)
            save(args.output/'RESULTS.json',{'status':'RUNNING' if record['valid'] else 'INFRASTRUCTURE_HOLD','rows':rows,
                'submitted_chat_requests':api.submitted_chat_requests,'freeze_sha256':identity})
            print(json.dumps({k:record.get(k) for k in ('id','valid','correct','stop_reason','infrastructure_hold','reported_usage')}),flush=True)
        if not record['valid']:break
    save(args.output/'RESULTS.json',{'status':'COMPLETED' if len(rows)==12 and all(r['valid'] for r in rows) else 'INFRASTRUCTURE_HOLD',
        'rows':rows,'submitted_chat_requests':api.submitted_chat_requests,'freeze_sha256':identity,
        'provider_generation_requests':None,'dollar_cost':None})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--connection',type=Path,required=True)
    p.add_argument('--credentials',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();remote=Remote(args.connection)
    try:run(args,remote)
    finally:remote.close()
