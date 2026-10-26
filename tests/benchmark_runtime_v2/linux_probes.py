"""Actual OS probes, synthetic sentinels only, no benchmark/model execution."""
import argparse
import json
import os
from pathlib import Path
import socket
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from integrations.benchmark_runtime_v2.sandbox import LinuxSandbox, SDK, Unsupported


def run(args):
    evidence = {"schema": "benchmark-runtime-v2-probes", "platform": sys.platform,
                "model_generation_calls": 0, "input_token_calls": 0, "rows": []}
    if sys.platform != "linux":
        try: LinuxSandbox()
        except Unsupported as exc:
            evidence.update(status="UNSUPPORTED_FAIL_CLOSED", reason=str(exc))
            return evidence
        raise AssertionError("Native non-Linux unexpectedly enabled")
    with tempfile.TemporaryDirectory(prefix="host-private-probes-") as name:
        outside = Path(name)
        targets = []
        for label in ("evaluation-reference", "other-slot", "user-private"):
            path = outside / label
            path.write_text("synthetic-not-a-real-secret", encoding="utf-8")
            targets.append(str(path))
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0)); listener.listen()
        port = listener.getsockname()[1]
        program = '''import errno,json,os,pathlib,socket
targets=TARGETS
rows=[]
for path in targets:
 for operation in ('read','write'):
  try:
   p=pathlib.Path(path)
   p.read_bytes() if operation=='read' else p.write_bytes(b'bad')
  except OSError as e:rows.append({'kind':operation,'errno':e.errno})
  else:raise AssertionError('Host path accessible')
for path in ('/outside-created','/input/probe.py','/usr/bin/python3'):
 try:pathlib.Path(path).write_bytes(b'bad')
 except OSError as e:rows.append({'kind':'write_readonly','errno':e.errno})
 else:raise AssertionError('Write escaped scratch')
assert 'HOST_ONLY_SENTINEL' not in os.environ
assert b'HOST_ONLY_SENTINEL' not in pathlib.Path('/proc/1/environ').read_bytes()
assert not pathlib.Path('/mnt').exists() and not pathlib.Path('/home').exists()
for address in [('127.0.0.1',PORT),('192.0.2.1',9)]:
 s=socket.socket();s.settimeout(.3)
 try:s.connect(address)
 except OSError as e:rows.append({'kind':'network','errno':e.errno})
 else:raise AssertionError('Network reachable')
 finally:s.close()
pathlib.Path('/work/allowed').write_text('ok')
pathlib.Path('/tmp/allowed').write_text('ok')
print(json.dumps(rows))
'''.replace("TARGETS", repr(targets)).replace("PORT", str(port))
        prior = os.environ.get("HOST_ONLY_SENTINEL")
        os.environ["HOST_ONLY_SENTINEL"] = "synthetic-environment-marker"
        try:
            sandbox = LinuxSandbox()
            result = sandbox.run({"probe.py": program.encode()}, ["/usr/bin/python3", "-I", "/work/project/probe.py"])
        finally:
            if prior is None: os.environ.pop("HOST_ONLY_SENTINEL", None)
            else: os.environ["HOST_ONLY_SENTINEL"] = prior
        assert result["exit"] == 0, result
        for path in targets: assert Path(path).read_text() == "synthetic-not-a-real-secret"
        evidence["rows"].append({"probe": "python_os_read_write_network_environment", "status": "PASS", "events": json.loads(result["stdout"]["text"])})
        limited = LinuxSandbox(wall_seconds=.15).run({"p.py": b"while True: pass"}, ["/usr/bin/python3", "/work/project/p.py"])
        assert limited["limit"] == "WALL_LIMIT", limited
        evidence["rows"].append({"probe": "wall_cleanup", "status": "PASS"})
        flooded = LinuxSandbox(output_limit=1024).run({"p.py": b"import os\nwhile True: os.write(1,b'x'*4096)"}, ["/usr/bin/python3", "/work/project/p.py"])
        assert flooded["limit"] == "OUTPUT_LIMIT" and flooded["stdout"]["truncated"], flooded
        evidence["rows"].append({"probe": "output_limit", "status": "PASS"})
        if not all((args.alva, args.toolchain, args.registry)):
            raise Unsupported("ALVA SDK required for compiler/generated-code validation")
        sdk = SDK(args.alva.resolve(), args.toolchain.resolve(), args.registry.resolve())
        # A new synthetic arithmetic fixture, never a P21/P3 replay or answer.
        rust = '''fn boundaries() {
 for path in TARGETS {
  assert!(std::fs::read(path).is_err());
  assert!(std::fs::write(path,b"bad").is_err());
 }
 assert!(std::fs::write("/escaped-generated-write",b"bad").is_err());
 let addr=std::net::SocketAddr::from(([127,0,0,1],PORT));
 assert!(std::net::TcpStream::connect_timeout(&addr,std::time::Duration::from_millis(200)).is_err());
}
'''.replace("TARGETS", json.dumps(targets)).replace("PORT", str(port))
        driver = '''import pathlib,subprocess
def command(args):
 p=subprocess.run(args,capture_output=True,text=True)
 assert p.returncode==0,(args,p.stdout,p.stderr)
command(['/sdk/alva','project','check','/work/project/alva.toml','--json'])
command(['/sdk/alva','project','build','/work/project/alva.toml','--out-dir','/work/generated'])
crate=pathlib.Path('/work/generated/isolated_probe')
probe=pathlib.Path('/input/probe.rs').read_text()
(crate/'build.rs').write_text(probe+'fn main(){boundaries();}')
with (crate/'src/lib.rs').open('a') as f:f.write(probe+'#[test] fn generated_runtime(){boundaries();assert_eq!(probe::plus(2,5),7);}')
command(['/sdk/toolchain/bin/cargo','test','--offline','--manifest-path',str(crate/'Cargo.toml')])
print('ALVA_CHECK_BUILD_BUILD_SCRIPT_GENERATED_TEST_PASS')
'''
        files = {"alva.toml": b'[project]\nname="isolated_probe"\n[modules]\n"probe"="src/probe.alva"\n',
                 "src/probe.alva": b'(module (name "probe") (version "0.1.0") (export plus) (fn plus (params (param a (prim i64)) (param b (prim i64))) (returns (prim i64)) (pure) (body (+ (ref a) (ref b)))))\n',
                 "driver.py": driver.encode(), "probe.rs": rust.encode()}
        result = LinuxSandbox(sdk).run(files, ["/usr/bin/python3", "-I", "/input/driver.py"])
        assert result["exit"] == 0 and "GENERATED_TEST_PASS" in result["stdout"]["text"], result
        for path in targets: assert Path(path).read_text() == "synthetic-not-a-real-secret"
        evidence["rows"].append({"probe": "alva_check_build_rust_build_script_and_generated_test", "status": "PASS"})
        listener.close()
    evidence.update(status="PASS", boundary="actual OS namespaces; outside reads ENOENT, writes EROFS/ENOENT, network unreachable/refused")
    return evidence


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--alva", type=Path); parser.add_argument("--toolchain", type=Path); parser.add_argument("--registry", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try: result = run(args)
    except Unsupported as exc: result = {"status": "UNSUPPORTED_FAIL_CLOSED", "reason": str(exc), "model_generation_calls": 0}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["status"] == "PASS" else 2)
