"""Trusted Linux draft evaluation. Candidate execution stays in P22 isolation."""
from __future__ import annotations

import json

from integrations.benchmark_runtime_v2.sandbox import LinuxSandbox
from integrations.codex.maintenance_host import canonical, sha


class LinuxProjectEvaluator:
    def __init__(self, sdk, crate, *, assertions="", wall_seconds=120):
        if not crate or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for c in crate):
            raise ValueError("Invalid trusted crate name")
        self.sdk, self.crate = sdk, crate
        self.assertions, self.wall_seconds = assertions, wall_seconds

    def identity(self):
        return sha(canonical({"alva": sha(self.sdk.alva.read_bytes()),
                              "rustc": sha((self.sdk.rust_toolchain / "bin/rustc").read_bytes()),
                              "suite": sha(self.assertions.encode()), "crate": self.crate,
                              "driver": sha(DRIVER.encode()), "wall_seconds": self.wall_seconds}))

    def __call__(self, snapshot, expected_revision):
        before = self.identity()
        config = {"crate": self.crate, "assertions": self.assertions,
                  "expected_revision": expected_revision, "paths": sorted(snapshot)}
        script = "CONFIG=" + repr(config) + "\n" + DRIVER
        execution = LinuxSandbox(self.sdk, wall_seconds=self.wall_seconds, output_limit=131072).run(
            snapshot, ["/usr/bin/python3", "-I", "-c", script])
        if execution["status"] != "EXECUTED" or execution["exit"] != 0:
            raise RuntimeError("ISOLATED_EVALUATOR_FAILURE")
        result = json.loads(execution["stdout"]["text"])
        if self.identity() != before: raise RuntimeError("EVALUATOR_CHANGED_DURING_EXECUTION")
        # Raw checker/build/test stdout stays with the trusted caller, never in
        # model-visible check statuses. The caller can persist this receipt.
        result["evaluator_identity"] = before
        return result


DRIVER = r'''
import hashlib,json,pathlib,subprocess
def fingerprint():
 values={p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest() for p in CONFIG['paths']}
 return hashlib.sha256(json.dumps(values,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()).hexdigest()
def run(argv):
 p=subprocess.run(argv,capture_output=True,text=True)
 return {'exit':p.returncode,'stdout':p.stdout[-6000:],'stderr':p.stderr[-6000:]}
fingerprint_before=fingerprint()
requests=[{'tool':'begin_transaction','project':'alva.toml','request_id':'draft-read'},
          {'tool':'abort_transaction','request_id':'draft-abort'}]
p=subprocess.run(['/sdk/alva','agent'],input=chr(10).join(json.dumps(r) for r in requests)+chr(10),capture_output=True,text=True)
# Build the JSON-lines input without relying on shell or source-file projection.
if p.returncode: raise RuntimeError('FRESH_AIR_READER_FAILED')
lines=[json.loads(line) for line in p.stdout.splitlines() if line.strip()]
if not lines or not lines[0].get('ok'):raise RuntimeError('FRESH_AIR_READER_REJECTED')
revision=lines[0]['result']['project_revision']
result={'status':'UNVERIFIED','project_revision':revision,'tested_snapshot_sha256':fingerprint_before,
        'checks':{'check':'NOT_RUN','build':'NOT_RUN','test':'NOT_RUN'},'work':{'fresh_native_reads':1,'commands':1}}
if revision!=CONFIG['expected_revision']:raise RuntimeError('DRAFT_REVISION_MISMATCH')
result['check']=run(['/sdk/alva','project','check','alva.toml','--json'])
result['work']['commands']+=1
result['checks']['check']='PASS' if result['check']['exit']==0 else 'FAIL'
if result['check']['exit']==0:
 result['build']=run(['/sdk/alva','project','build','alva.toml','--out-dir','/work/generated'])
 result['work']['commands']+=1
 result['checks']['build']='PASS' if result['build']['exit']==0 else 'FAIL'
 if result['build']['exit']==0:
  crate=pathlib.Path('/work/generated')/CONFIG['crate']
  if CONFIG['assertions']:
   with (crate/'src/lib.rs').open('a') as f:f.write(CONFIG['assertions'])
  result['test']=run(['/sdk/toolchain/bin/cargo','test','--offline','--manifest-path',str(crate/'Cargo.toml')])
  result['work']['commands']+=1
  result['checks']['test']='PASS' if result['test']['exit']==0 else 'FAIL'
result['status']='PASS' if all(v=='PASS' for v in result['checks'].values()) else 'FAIL'
if fingerprint()!=fingerprint_before:raise RuntimeError('DRAFT_MUTATED_DURING_TESTS')
print(json.dumps(result))
'''
