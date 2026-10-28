"""MM01-only host evaluator. Assertions never enter candidate namespaces.

Exact goal/regression strings are extracted from P29 at prepare time and bound
in FREEZE. No engineering edit path is imported into the executing service.
"""
import json
from integrations.benchmark_runtime_v2.sandbox import LinuxSandbox


def evaluate(snapshot, sdk, assertions, check_only=False):
    driver = '''import json,pathlib,subprocess
def run(args):
 p=subprocess.run(args,capture_output=True,text=True)
 return {"exit":p.returncode,"stdout":p.stdout[-12000:],"stderr":p.stderr[-12000:]}
r={"check":run(["/sdk/alva","project","check","alva.toml","--json"])}
if r["check"]["exit"]:r["status"]="COMPILE_FAIL"
elif CHECK_ONLY:r["status"]="PASS"
else:
 r["build"]=run(["/sdk/alva","project","build","alva.toml","--out-dir","/work/generated"])
 if r["build"]["exit"]:r["status"]="COMPILE_FAIL"
 else:
  crate=pathlib.Path("/work/generated/demo")
  with (crate/"src/lib.rs").open("a") as f:f.write(ASSERTIONS["regression"]+ASSERTIONS["goal"])
  cargo=["/sdk/toolchain/bin/cargo","test","--offline","--manifest-path",str(crate/"Cargo.toml")]
  r["regression"]=run(cargo+["maintenance_regression::"])
  r["goal"]=run(cargo+["maintenance_goal::"])
  r["status"]="PASS" if r["goal"]["exit"]==r["regression"]["exit"]==0 else "TEST_FAIL"
print(json.dumps(r))
'''.replace("CHECK_ONLY", repr(check_only)).replace("ASSERTIONS", repr(assertions))
    raw = LinuxSandbox(sdk, wall_seconds=120, output_limit=131072).run(
        snapshot, ["/usr/bin/python3", "-I", "-c", driver])
    if raw["status"] != "EXECUTED" or raw["exit"] != 0:
        raise RuntimeError("ISOLATED_EVALUATOR_FAILURE:" + json.dumps(raw))
    return json.loads(raw["stdout"]["text"])
