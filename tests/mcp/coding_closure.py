"""Trusted host: materialize exact P24 inputs, run all witness code in P23."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from integrations.benchmark_runtime_v2.freeze import pack_git
from integrations.benchmark_runtime_v2.persistent import PersistentSandbox
from integrations.benchmark_runtime_v2.sandbox import SDK, Unsupported

BASE = "837226e69262d37c6e5fd5af5465790066bd7211"


def run(args):
    if sys.platform != "linux":
        try:
            PersistentSandbox({}, "not-a-bundle")
        except Unsupported as exc:
            return {
                "status": "UNSUPPORTED_FAIL_CLOSED",
                "reason": str(exc),
                "generation_calls": 0,
            }
        raise AssertionError("Native non-Linux enabled")
    paths = [
        f"benchmarks/native_mcp_skill/inputs/{case}/{path}"
        for case in ("HE41", "HE23", "HE42", "HE3")
        for path in ("alva.toml", "src/task.alva")
    ]
    paths.append("tests/mcp/mcp_protocol_test.py")  # reuse its public stdio client only
    bundle = pack_git(args.repo, BASE, paths)
    driver = (Path(__file__).with_name("coding_closure_inside.py")).read_bytes()
    sdk = SDK(args.alva.resolve(), args.toolchain.resolve(), args.registry.resolve())
    with PersistentSandbox(
        bundle, bundle["payload_sha256"], sdk, output_limit=8 * 1024**2
    ) as box:
        versions = {
            name: box.run(["/sdk/toolchain/bin/" + name, "--version"])["stdout"].strip()
            for name in ("rustc", "cargo")
        }
        result = box.run(["/usr/bin/python3", "-I", "-c", driver.decode("utf-8")])
    evidence = json.loads(result["stdout"])
    evidence.update(
        input_commit=BASE,
        input_bundle_sha256=bundle["payload_sha256"],
        driver_sha256=hashlib.sha256(driver).hexdigest(),
        binary_sha256=hashlib.sha256(sdk.alva.read_bytes()).hexdigest(),
        execution_backend="P23 PersistentSandbox -> Linux namespaces; all MCP children/builds/tests inside",
        toolchain=versions,
    )
    return evidence


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=ROOT)
    parser.add_argument("--alva", type=Path)
    parser.add_argument("--toolchain", type=Path)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        evidence = run(args)
    except Unsupported as exc:
        evidence = {
            "status": "UNSUPPORTED_FAIL_CLOSED",
            "reason": str(exc),
            "generation_calls": 0,
            "input_token_calls": 0,
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(evidence, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(
        json.dumps(
            {
                "status": evidence["status"],
                "cases": [
                    {"case": c["case"], "status": c["status"]}
                    for c in evidence.get("cases", [])
                ],
                "generation_calls": 0,
            }
        )
    )
    raise SystemExit(0 if evidence["status"] == "PASS" else 2)
