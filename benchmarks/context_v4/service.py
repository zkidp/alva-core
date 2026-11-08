import argparse,copy,json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from benchmarks.context_v4.protocol import design,tools
from benchmarks.host_v3_acceptance.service import Session as BaseSession
from integrations.codex.maintenance_context import References,source_read
from integrations.benchmark_runtime_v2.sandbox import SDK
from integrations.codex.maintenance_host import sha


class Session(BaseSession):
    def __init__(self,task,arm,sdk):
        super().__init__(task,arm,sdk)
        self.references=References()
    def tool(self,name,args):
        if name in ('read_reference','read_source'):
            value=self.references.read(args) if name=='read_reference' else source_read(self.text if self.arm=='T' else self.original,args,
                'ACKNOWLEDGED_SOURCE_PROPOSAL' if self.arm=='T' else 'IMPORT_SOURCE_NOT_STAGED_AIR')
            self.calls.append({'name':name,'arguments':args,'trusted_result':value})
            return value
        if name not in ('read_target','prepare_change','publish_change'):
            return {'status':'REJECTED','reason':'TOOL_NOT_EXPOSED'}
        result=super().tool(name,args)
        if name=='read_target' and self.arm!='V3' and result.get('structuredContent',{}).get('status')=='READY':
            value=copy.deepcopy(result['structuredContent'])
            value['body_syntax']=self.references.sections['language']['body']
            result['structuredContent']=value
        return result


def serve(args):
    from benchmarks.maintenance_interface_comparison.linux_profile import install
    install();sdk=SDK(*(Path(getattr(args,k)).resolve() for k in ('alva','toolchain','registry')))
    session=Session(design()['tasks'][args.task],args.arm,sdk)
    print(json.dumps({'ready':True,'tools':tools(args.arm),'alva_sha256':sha(sdk.alva.read_bytes())}),flush=True)
    try:
        for line in sys.stdin:
            req=json.loads(line)
            if req['action']=='finish':print(json.dumps(session.finish()),flush=True);break
            if req['action']!='tool':raise RuntimeError('UNSUPPORTED_TRUSTED_ACTION')
            print(json.dumps(session.tool(req['name'],req['arguments'])),flush=True)
    finally:session.close()


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for k in ('task','arm','alva','toolchain','registry'):p.add_argument('--'+k,required=True)
    serve(p.parse_args())
