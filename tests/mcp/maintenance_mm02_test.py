#!/usr/bin/env python3
"""Deterministic prototype witness on original MM02. Never an agent success.

Reuses original public bundle, independent assertions and actual P34 Guard.
The body witness is host-only; it must never be mounted in a model session.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from maintenance_profile_test import Client, TOOLS
from benchmarks.maintenance_design import feasibility as prior, witnesses
from benchmarks.native_prospective.service import files
from benchmarks.p34_scope_guard.cases import case
from integrations.benchmark_runtime_v2.freeze import decode
from integrations.benchmark_runtime_v2.persistent import PersistentSandbox
from integrations.benchmark_runtime_v2.sandbox import SDK
from integrations.codex.precommit_scope_guard import GuardedNative


class ProfileBox(PersistentSandbox):
    def _command(self, argv):
        if argv == ["/sdk/alva", "mcp"]:
            argv = [*argv, "--profile", "maintenance"]
        return super()._command(argv)


def form_end(text, start):
    """Bounded fixture extraction; no ALVA rewrite or alternative interpreter."""
    depth, quoted, escaped, comment = 0, False, False, False
    for i in range(start, len(text)):
        c = text[i]
        if comment:
            comment = c != "\n"
        elif quoted:
            if escaped:
                escaped = False
            elif c == "\\":
                escaped = True
            elif c == '"':
                quoted = False
        elif c == ';':
            comment = True
        elif c == '"':
            quoted = True
        elif c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0:
                return i + 1
    raise ValueError("Unclosed engineering fixture")


def main(args):
    if sys.platform != "linux":
        raise RuntimeError("Linux namespace execution required; no host fallback")
    if args.shared_uid_profile:
        # Reuse the prospective shared-host resource adjustment; no frozen edits.
        from benchmarks.maintenance_interface_comparison.linux_profile import install
        install()
    sdk = SDK(*(Path(getattr(args, k)).resolve() for k in ("alva", "toolchain", "registry")))
    fixed = case("MM02_SHARED")
    task, bundle = fixed["task"], fixed["bundle"]
    expected = "352a8b6fa459942b8b1d5469a966a706498afa7a2abbc13c39c457dafb069faf"
    assert bundle["payload_sha256"] == expected
    original = decode(bundle, expected)
    # Existing deterministic source witness, used only to extract one body.
    # Original source, manifest and shared graph remain untouched in the box.
    text = witnesses.text_change("MM02", original)["src/xml.alva"].decode()
    start = text.index("  (fn parse_prefix")
    body_start = text.index("(body", start)
    assert body_start < form_end(text, text.index("(fn", start))
    replacement = text[body_start:form_end(text, body_start)]
    ledger = []
    with ProfileBox(bundle, expected, sdk, wall_seconds=600, rpc_seconds=30) as box:
        assert files(box) == original
        baseline_task = prior.evaluate(box, task["crate"], witnesses.goals("MM02"))
        baseline_regression = prior.evaluate(box, task["crate"], witnesses.regressions("MM02"))
        assert baseline_task["status"] == "TEST_FAIL", baseline_task
        assert baseline_regression["status"] == "PASS", baseline_regression
        with GuardedNative(box.mcp(), fixed["policy"], TOOLS, ledger.append) as native:
            prior.initialize(native)
            schemas = native.request("tools/list")["tools"]
            assert tuple(t["name"] for t in schemas) == TOOLS
            c = Client(native, "/work/project/alva.toml")
            def bodies(client):
                return {f: client.call("inspect_entity", entity=f)["slots"]["body"][0]
                        for f in task["functions"]}
            before = bodies(c)
            initial_project = c.call("inspect_project")
            descriptor = c.function(task["target"])
            # The new read operation yields a directly editable body fragment.
            assert not c.replace(task["target"], descriptor["body"], descriptor["body_revision"])["isError"]
            assert bodies(c) == before, "body projection must round trip without changing AIR"
            result = c.replace(task["target"], replacement, descriptor["body_revision"])
            assert not result["isError"], result
            staged = bodies(c)
            changed = [f for f in before if before[f] != staged[f]]
            assert changed == [task["target"]], changed
            preview = c.call("preview_semantic_diff")
            checked = c.call("check_transaction")
            assert checked == {"problems": []}
            assert files(box) == original, "staging cannot publish or change source"
            commit = c.call("commit_transaction")
            assert commit["host_scope"]["status"] == "SCOPE_ALLOWED", commit
        published = files(box)
        assert all(published[p] == data for p, data in original.items())
        assert "alva-air/current" in published
        with box.mcp() as native:
            prior.initialize(native)
            r = Client(native, "/work/project/alva.toml")
            fresh = bodies(r)
            final_project = r.call("inspect_project")
            r.call("abort_transaction")
        assert fresh == staged
        assert final_project["project_revision"] == commit["revision"]
        goal = prior.evaluate(box, task["crate"], witnesses.goals("MM02"))
        regression = prior.evaluate(box, task["crate"], witnesses.regressions("MM02"))
        assert goal["status"] == regression["status"] == "PASS", (goal, regression)
    dispatches = [e for e in ledger if e["event"] == "native_dispatch"
                  and e.get("params", {}).get("name") == "commit_transaction"]
    assert len(dispatches) == 1
    prior.save(args.output, {"status": "PASS", "kind": "DETERMINISTIC_PROTOTYPE_WITNESS",
        "model_generation_calls": 0, "input_token_api_calls": 0,
        "original_bundle_sha256": expected, "tools": TOOLS,
        "baseline_task": baseline_task["status"], "baseline_regression": baseline_regression["status"],
        "before_body_revisions": before, "staged_body_revisions": staged,
        "fresh_body_revisions": fresh, "changed_functions": changed, "preview": preview,
        "check": checked, "commit": commit, "actual_native_commits": len(dispatches),
        "source_unchanged": True, "initial_project": initial_project, "fresh_project": final_project,
        "task": goal, "regression": regression, "guard_ledger": ledger})
    print("PASS: original MM02, body replacement, P34 Guard, one Native commit, fresh AIR, independent task/regression")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for k in ("alva", "toolchain", "registry"):
        p.add_argument("--" + k, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--shared-uid-profile", action="store_true")
    main(p.parse_args())
