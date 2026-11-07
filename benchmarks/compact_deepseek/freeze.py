"""Freeze independently registered DeepSeek runtime before any model call."""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys

from benchmarks.compact_deepseek.preflight import design
from benchmarks.compact_deepseek.api import API
from benchmarks.compact_deepseek.runner import save
from benchmarks.compact_maintenance.contract import study_tools
from benchmarks.p36_mm02_native_model.remote import Remote
from integrations.benchmark_runtime_v2.freeze import sha

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).parent


def main(args):
    target = HERE / "FREEZE.json"
    if target.exists():
        raise RuntimeError("Existing freeze is immutable")
    preflight = json.loads(args.preflight.read_bytes())
    assert preflight["status"] == "PASS" and preflight["model_generation_calls"] == 0
    assert len(preflight["rows"]) == 8 and all(r["status"] == "PASS" and r["cleanup"]["confirmed"] for r in preflight["rows"])
    remote, api = Remote(args.connection), API(args.credentials)
    metadata = api.request("/models")
    selected = next(m for m in metadata["data"] if m["id"] == "deepseek-flash")
    assert "low" in selected["effort"]["supported_levels"]
    frozen = design()
    frozen["status"] = "FROZEN_BEFORE_GENERATION"
    frozen["model_metadata"] = selected
    frozen["model_metadata_sha256"] = sha(json.dumps(metadata, sort_keys=True).encode())
    frozen["registration_commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    frozen["preflight_sha256"] = sha(args.preflight.read_bytes())
    frozen["provider_tools"] = {}
    for arm in ("T", "N"):
        tools = study_tools(arm)
        if arm == "N":
            native = [r["native_schemas"] for r in preflight["rows"] if r["arm"] == "N"]
            assert all(n == native[0] for n in native)
            tools += native[0]
        frozen["provider_tools"][arm] = [{"type": "function", "function": {
            "name": t["name"], "description": t["description"], "parameters": t["inputSchema"]}} for t in tools]
    code = set(subprocess.check_output(["git", "ls-files", "*.py"], cwd=ROOT, text=True).splitlines())
    code.update(p.relative_to(ROOT).as_posix() for p in HERE.glob("*.py"))
    frozen["runtime_files"] = {p: sha((ROOT / p).read_bytes()) for p in sorted(code)}
    frozen["controller_python_sha256"] = sha(Path(sys.executable).read_bytes())
    sdk = remote.cfg["sdk_paths"]
    frozen["sdk_executables"] = json.loads(remote.checked(["python3", "-c",
        "import pathlib,hashlib,json,sys;print(json.dumps({k:hashlib.sha256(pathlib.Path(v).read_bytes()).hexdigest() for k,v in json.load(sys.stdin).items()}))"],
        input=json.dumps({"alva": sdk["alva"], "rustc": sdk["toolchain"] + "/bin/rustc"})))
    tree_code = """import hashlib,json,pathlib,sys
out={}
for name,path in json.load(sys.stdin).items():
 root=pathlib.Path(path); rows=[]
 for p in sorted(root.rglob('*')):
  if p.is_file(): rows.append((p.relative_to(root).as_posix(),hashlib.sha256(p.read_bytes()).hexdigest()))
 out[name]={'files':len(rows),'sha256':hashlib.sha256(json.dumps(rows,separators=(',',':')).encode()).hexdigest()}
print(json.dumps(out))"""
    frozen["sdk_trees"] = json.loads(remote.checked(["python3", "-c", tree_code],
        input=json.dumps({"toolchain": sdk["toolchain"], "registry": sdk["registry"]}), timeout=180))
    frozen["runtime_freeze"] = "this independent DeepSeek freeze; original MIC-02 GPT design is unchanged"
    save(target, frozen)
    save(HERE / "PREFLIGHT.json", {"status": "PASS", "model_generation_calls": 0,
        "input_token_api_calls": 0, "raw_preflight_sha256": sha(args.preflight.read_bytes()),
        "rows": [{k: r[k] for k in ("id", "task", "arm", "status", "outcome", "evidence_sha256")} for r in preflight["rows"]]})
    print(json.dumps({"status": frozen["status"], "model": frozen["model"], "slots": len(frozen["schedule"]),
                      "runtime_files": len(code), "model_generation_calls": 0, "freeze_sha256": sha(target.read_bytes())}))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--connection", required=True, type=Path)
    p.add_argument("--credentials", required=True, type=Path)
    p.add_argument("--preflight", required=True, type=Path)
    main(p.parse_args())
