"""Zero-provider qualification and actual input freeze. No credential access."""
import argparse
import copy
import json
from pathlib import Path
import platform
import subprocess
import sys
import tempfile

from benchmarks.context_flash_pilot.tasks import tasks
from benchmarks.context_flash_pilot.service import Session, advertised_tools
from benchmarks.maintenance_interface_comparison.service import evaluate
from integrations.codex.maintenance_context import References, TOOLS
from integrations.codex.maintenance_host import canonical, sha
from integrations.benchmark_runtime_v2.freeze import decode
from integrations.benchmark_runtime_v2.sandbox import SDK

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).parent
MODEL = "deepseek-flash"
PARAMETERS = {"thinking": {"type": "enabled"}, "reasoning_effort": "low", "max_tokens": 4096, "stream": False}
LIMITS = {"requests": 12, "tools": 36, "token_observation": 120000, "output_cap": 4096,
          "request_bytes": 131072, "active_seconds": 480, "request_timeout": 90, "concurrency": 1}
INSTRUCTIONS = '''Maintain only the authorized ALVA target body under the public requirement.
Use the advertised source/context/reference tools as needed; complete public source and shared documentation remain accessible.
read_target provides the view_id. prepare_change accepts one full ALVA (body ...) fragment, not an entire function/module.
Host owns revision/scope control, isolated compiler/build/behavior checks and publication. Repair rejected candidates within the same view.
Publish the PREPARED proposal once with publish_change. Preparation is not publication. A published-but-unverified result is not success.
No shell, arbitrary filesystem, evaluator source, test changes, other sessions or operator recovery are available.
Finite tests and bounded structural context are not completeness proofs; use source fallback when needed.
Limits: 12 generation requests, 36 dispatched tool calls, 480 active seconds, 120000 cumulative reported-token observation threshold, 4096 output cap, 131072 serialized request bytes. Token observation is NOT a provider hard cumulative limit. Completed responses drain legal actions subject to tool/wall/safety limits, then no next request if exhausted.
Normal completion without publication or a resource stop ends this single attempt. No retries or replacements.
'''


def tools():
    result = advertised_tools()
    return [{"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["inputSchema"]}} for t in result]


def messages(frozen, task):
    return [{"role": "system", "content": frozen["instructions"] + "\n" + frozen["host_skill"]},
            {"role": "user", "content": json.dumps({"task": task["public_task"], "source_paths": task["input_paths"]}, ensure_ascii=False)}]


def runtime():
    # Pin actual runtime checkout bytes; no cross-platform newline normalization.
    return {p.relative_to(ROOT).as_posix(): sha(p.read_bytes()) for directory in ("benchmarks", "integrations")
            for p in sorted((ROOT / directory).rglob("*.py")) if "__pycache__" not in p.parts}


def qualify(sdk, catalog):
    # Engineering candidates are ONLY qualification inputs, never model context.
    candidates = {
        "Q01": '(body (if (< (ref subtotal) (int 0)) (int 0) (if (< (ref cap) (int 0)) (int 0) (if (< (ref subtotal) (ref cap)) (ref subtotal) (ref cap)))))',
        "Q02": '(body (let mass (field (field (ref request) "parcel") "mass") (if (<= (ref mass) (int 0)) (int 0) (+ (call rates.base (ref mass)) (if (field (ref request) "priority") (int 20) (int 0))))))',
        "Q03": '(body (if (< (ref attempts) (int 0)) (int 0) (let value (+ (call policy.base (ref attempts)) (int 3)) (if (> (ref value) (int 20)) (int 20) (ref value)))))'}
    rows = []
    for ident, task in catalog.items():
        source = decode(task["bundle"], task["bundle"]["payload_sha256"])
        baseline = evaluate(source, sdk, task)
        if baseline["goal"]["status"] != "TEST_FAIL" or baseline["regression"]["status"] != "PASS":
            raise RuntimeError("BASELINE_QUALIFICATION:" + ident + ":" + json.dumps(baseline))
        for arm in ("A", "B", "C"):
            session = Session(task, arm, sdk)
            try:
                symbols = session.tool("list_symbols", {})
                if symbols["modules"] != task["policy"]["modules"]: raise RuntimeError("SYMBOL_COVERAGE")
                if not session.tool("search_source", {"text": "(fn "})["hits"]: raise RuntimeError("SEARCH_POSITIVE")
                if session.tool("search_source", {"text": "__absent_token__"})["hits"]: raise RuntimeError("SEARCH_EMPTY")
                read = session.tool("read_target", {"function": task["public_task"]["target"]})
                if read["status"] != "READY": raise RuntimeError("TARGET_NOT_READY")
                if arm == "A" and "context" in read: raise RuntimeError("A_CONTEXT_LEAK")
                if arm == "C" and read["bounded_dependencies"]["status"] != "COMPLETE_WITHIN_BOUNDARY": raise RuntimeError("C_CONTEXT")
                proposal = session.tool("prepare_change", {"view_id": read["view_id"], "body": candidates[ident]})
                if proposal["status"] != "PREPARED": raise RuntimeError("QUALIFIED_CHANGE_REJECTED:" + json.dumps(proposal))
                published = session.tool("publish_change", {"proposal_id": proposal["proposal_id"]})
                if published["status"] != "PUBLISHED": raise RuntimeError("QUALIFICATION_PUBLICATION")
                final = session.finish()
                if not final["correct"] or not final["original_sources_unchanged"]: raise RuntimeError("FINAL_QUALIFICATION")
                rows.append({"task": ident, "arm": arm, "baseline_goal": "TEST_FAIL", "baseline_regression": "PASS",
                             "engineering_publication": "PASS", "independent_final": "PASS", "source_unchanged": True})
            finally: session.close()
    return rows


def build(sdk, base):
    catalog = tasks()
    rows = qualify(sdk, catalog)
    ref = References()
    result = {"schema": "context-flash-development/v1", "status": "FROZEN_BEFORE_MODEL",
        "authorship": "Codex-authored maintenance fixtures; not external real-repository or independent holdout samples",
        "base": base,
        "tasks": catalog, "instructions": INSTRUCTIONS, "host_skill": ref.docs["host"], "reference_docs": ref.docs,
        "provider_tools": tools(), "model": MODEL, "api_parameters": PARAMETERS, "limits": LIMITS,
        "sdk": {"alva_sha256": sha(sdk.alva.read_bytes()), "rustc_sha256": sha((sdk.rust_toolchain / "bin/rustc").read_bytes())},
        "runtime": runtime(), "qualification": rows, "runtime_python": platform.python_version(),
        "schedule": [{"id": ident + "-" + arm, "task": ident, "arm": arm}
                     for ident, order in zip(catalog, (("A", "B", "C"), ("C", "A", "B"), ("B", "C", "A"))) for arm in order],
        "screens": {"all_pairs_reported": True, "correct_not_lower_than_A": True, "median_total_C_over_A_at_most": .75,
            "worst_total_C_over_A_at_most": 1.5, "raw_source_reduction": True,
            "note": "Exploratory engineering screen; no significance/generalization; failures not removed from total-cost accounting"},
        "surface_limits": "A is a matched source-acquisition control with literal search and generic symbol index, not a full IDE/LSP baseline; identical structured body mutation in all arms. No broad conventional-tool superiority claim."}
    result["initial_inputs"] = {ident: messages(result, task) for ident, task in catalog.items()}
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for k in ("alva", "toolchain", "registry", "output"): p.add_argument("--" + k, type=lambda s: Path(s).resolve(), required=True)
    p.add_argument("--base", required=True)
    args = p.parse_args()
    if len(args.base) != 40 or any(c not in "0123456789abcdef" for c in args.base): p.error("Exact trusted base commit required")
    result = build(SDK(args.alva, args.toolchain, args.registry), args.base)
    with args.output.open("x", encoding="utf-8") as f: json.dump(result, f, indent=2)
    print(json.dumps({"status": result["status"], "qualified": len(result["qualification"]), "generation_calls": 0}))
