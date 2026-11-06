"""Bind successful no-model probes and runtime before any generation."""
import argparse
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from benchmarks.maintenance_interface_comparison.pilot import HERE, INSTRUCTIONS, TOOLS, save
from integrations.benchmark_runtime_v2.freeze import sha


def main(args):
    target = HERE / "FREEZE.json"
    if target.exists():
        raise RuntimeError("Existing freeze must not be overwritten")
    baseline = json.loads(args.preflight.read_text())
    probe = json.loads(args.probe.read_text())
    assert baseline["status"] == probe["status"] == "PASS"
    assert baseline["model_generation_calls"] == probe["generation_calls"] == 0
    assert len(baseline["rows"]) == 6 and all(r["status"] == "PASS" for r in baseline["rows"])
    registered = json.loads((HERE / "REGISTRATION.json").read_text())
    assert all(r["actual_model"] == registered["model"] for r in probe["rows"])
    frozen = copy.deepcopy(registered)
    code = set(subprocess.check_output(["git", "ls-files", "*.py"], cwd=ROOT, text=True).splitlines())
    code.update(p.relative_to(ROOT).as_posix() for p in HERE.glob("*.py"))
    frozen.update(schema="mic01-freeze/v1", status="FROZEN_BEFORE_GENERATION", preflight_status="PASS",
        registration_commit="4678392", registration_sha256=sha((HERE / "REGISTRATION.json").read_bytes()),
        protocol_sha256=sha((HERE / "PROTOCOL.md").read_bytes()), developer_instructions=INSTRUCTIONS, study_tools=TOOLS,
        sdk_identity=baseline["sdk_identity"], resource_profile=baseline["resource_profile"],
        runtime_files={p: sha((ROOT / p).read_bytes()) for p in sorted(code)},
        codex=subprocess.check_output([shutil.which("codex"), "--version"], text=True).strip(),
        codex_binary_sha256=sha(Path(shutil.which("codex")).read_bytes()),
        preflight_sha256=sha(args.preflight.read_bytes()), technical_probe_sha256=sha(args.probe.read_bytes()))
    save(target, frozen)
    save(HERE / "PREFLIGHT.json", {"status": "PASS", "baseline_tasks": [{"id": r["id"], "goal": r["evaluation"]["goal"]["status"],
        "regression": r["evaluation"]["regression"]["status"], "native_schema_sha256": r["native_schema_sha256"],
        "text_full_file_writer": r["text_full_file_writer"]} for r in baseline["rows"]], "host_probe": probe,
        "resource_profile": baseline["resource_profile"], "sdk_identity": baseline["sdk_identity"],
        "preparation_model_generation_calls": 0, "preparation_input_token_api_calls": 0})
    print(json.dumps({"freeze_sha256": sha(target.read_bytes()), "runtime_files": len(code), "slots": 24}))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--preflight", required=True, type=Path)
    p.add_argument("--probe", required=True, type=Path)
    main(p.parse_args())
