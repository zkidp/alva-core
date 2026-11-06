"""No-model Linux qualification and exact SDK identities; no candidate fallback."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import traceback

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from benchmarks.maintenance_interface_comparison import service
from integrations.benchmark_runtime_v2.sandbox import SDK, LinuxSandbox
from integrations.benchmark_runtime_v2.persistent import PersistentSandbox
from integrations.benchmark_runtime_v2.freeze import canonical, decode, sha
from benchmarks.maintenance_design import feasibility as prior


def tree_identity(path):
    rows = [(p.relative_to(path).as_posix() if path.is_dir() else path.name, sha(p.read_bytes()))
            for p in sorted(path.rglob("*")) if p.is_file()] if path.is_dir() else [(path.name, sha(path.read_bytes()))]
    return {"sha256": sha(canonical(rows)), "files": len(rows)}


def main(args):
    sdk = SDK(*(Path(getattr(args, k)).resolve() for k in ("alva", "toolchain", "registry")))
    registration = json.loads((Path(__file__).parent / "REGISTRATION.json").read_text())
    results = []
    for ident, task in registration["tasks"].items():
        row = {"id": ident}
        try:
            with PersistentSandbox(task["bundle"], task["bundle"]["payload_sha256"], sdk) as box:
                initial = service.inspect(box, task)
                assert "error" not in initial, initial
                with box.mcp() as native:
                    prior.initialize(native)
                    schemas = native.request("tools/list")["tools"]
                    assert len(schemas) == 20
                # Actual isolated full-file writer and read/Git-diff route.
                from integrations.benchmark_runtime_v2.persistent import _Process
                lines = service.old.Lines.__new__(service.old.Lines)
                lines.box = box
                lines.proc = _Process(box, ["/usr/bin/python3", "-I", "-c", service.inside_source(task["input_paths"])])
                call = lines.call
                revision = call("revision", {})
                source = decode(task["bundle"], task["bundle"]["payload_sha256"])
                target = next(p for p in task["input_paths"] if p.endswith(".alva"))
                written = call("write", {"revision": revision["revision"], "path": target, "content": source[target].decode()})
                assert written["accepted"]
                diff = call("diff", {"revision": written["revision"]})
                assert diff["diff"] == ""
                lines.close()
            evaluation = service.evaluate(source, sdk, task)
            assert evaluation["goal"]["status"] == "TEST_FAIL" and evaluation["regression"]["status"] == "PASS", evaluation
            row.update(status="PASS", baseline=initial, evaluation=evaluation, native_schema_sha256=sha(canonical(schemas)), text_full_file_writer="PASS")
        except Exception as exc:
            row.update(status="BLOCKED", reason=type(exc).__name__ + ":" + str(exc), traceback=traceback.format_exc())
        results.append(row)
        print(json.dumps({"id": ident, "status": row["status"], "reason": row.get("reason")}), flush=True)
    result = {"status": "PASS" if all(r["status"] == "PASS" for r in results) else "BLOCKED",
        "model_generation_calls": 0, "input_token_api_calls": 0, "platform": platform.platform(),
        "sdk_identity": {"binary": tree_identity(sdk.alva), "toolchain": tree_identity(sdk.rust_toolchain), "registry": tree_identity(sdk.registry)},
        "alva_version": subprocess.check_output([str(sdk.alva), "--version"], text=True).strip(),
        "rows": results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print("PREFLIGHT=" + json.dumps({k: v for k, v in result.items() if k != "rows"}), flush=True)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for name in ("alva", "toolchain", "registry"):
        p.add_argument("--" + name, required=True)
    p.add_argument("--output", type=Path, required=True)
    raise SystemExit(main(p.parse_args()))
