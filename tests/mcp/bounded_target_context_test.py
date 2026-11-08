"""Real AEP/Guard/read-context test. No provider, task answer or historical run.

Windows: actual Core inspection; receipt stub only for lifecycle (explicit).
Linux --toolchain/--registry: real existing OS-isolated compilation + assertions.
"""
import argparse
import copy
import io
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from integrations.codex.bounded_target_context import BoundedTargetHost
from integrations.codex.maintenance_context import ContextHost, TOOLS, serve
from integrations.codex.maintenance_host import AgentProcess, MaintenanceHost, project_source_loader
from tests.mcp.host_workflow_test import ReceiptEvaluator

SOURCE = '''(module (name "m") (version "1") (export target helper)
 (type Flag (enum (variant on) (variant off)))
 (type Alias (alias Flag))
 (type Item (record (field flag Alias)))
 (fn helper (params (param item Item)) (returns (prim i64)) (pure)
   (body (int 7)))
 (fn target (params (param item Item)) (returns (prim i64)) (pure)
   (body (call helper (ref item)))))'''


def run(binary, sdk=None):
    with tempfile.TemporaryDirectory(prefix="bounded-dependencies-") as tmp:
        root = Path(tmp)
        (root / "alva.toml").write_text('[project]\nname="context_demo"\n[modules]\nm="m.alva"\n', encoding="utf-8")
        (root / "m.alva").write_text(SOURCE, encoding="utf-8")
        sources = project_source_loader(root / "alva.toml", ["alva.toml", "m.alva"])
        original = sources()
        policy = {"authorized_functions": ["m.target"], "modules": {"m": {"functions": ["helper", "target"], "types": ["Flag", "Alias", "Item"]}}}
        if sdk:
            from integrations.codex.maintenance_evaluator import LinuxProjectEvaluator
            evaluator = LinuxProjectEvaluator(sdk, "context_demo", assertions='''
#[test] fn scoped_target() {
 let item = crate::m::Item { flag: crate::m::Flag::On };
 assert_eq!(crate::m::target(item.clone()), 8);
 assert_eq!(crate::m::helper(item), 7);
}''')
        else:
            evaluator = ReceiptEvaluator()
        base = MaintenanceHost(lambda: AgentProcess(binary), root / "alva.toml", policy, sources, evaluator)
        host = BoundedTargetHost(base)
        try:
            ready = host.invoke("read_target", {"function": "m.target"})
            assert ready["status"] == "READY", ready
            context = ready["bounded_dependencies"]
            assert context["status"] == "COMPLETE_WITHIN_BOUNDARY", context
            assert [t["name"] for t in context["types"]] == ["m.Alias", "m.Flag", "m.Item"]
            assert context["callees"][0]["function"] == "m.helper"
            assert ready["dependency_projection_work"]["native_calls"] == 3
            assert not (root / "alva-air/current").exists()
            assert sources() == original
            incoming = io.StringIO("\n".join(json.dumps({"jsonrpc": "2.0", "id": i, "method": method, **extra})
                for i, (method, extra) in enumerate([
                    ("initialize", {}), ("tools/list", {}),
                    ("tools/call", {"params": {"name": "read_target", "arguments": {"function": "m.target"}}})])))
            output = io.StringIO()
            serve(host, incoming, output)
            replies = [json.loads(line) for line in output.getvalue().splitlines()]
            assert replies[1]["result"]["tools"] == TOOLS
            assert replies[2]["result"]["isError"] is False
            assert replies[2]["result"]["structuredContent"]["bounded_dependencies"] == context
            before, air = base._export()
            again = host.invoke("read_target", {"function": "m.target"})
            after, air_after = base._export()
            assert before == after and air == air_after, "context must not mutate any graph bytes"
            assert context == again["bounded_dependencies"]
            # Missing context data cannot be promoted to complete; ordinary
            # editing remains on the original Host admission path.
            call = base._call
            def bad_snapshot(name, **args):
                result = call(name, **args)
                if name == "inspect_scope_snapshot":
                    result = copy.deepcopy(result)
                    result["nodes"].pop(next(iter(result["nodes"])))
                return result
            base._call = bad_snapshot
            try:
                failed = host.invoke("read_target", {"function": "m.target"})
                assert failed["bounded_dependencies"]["status"] == "UNKNOWN", failed
                assert not base.blocked
            finally:
                base._call = call
            def changed_project(name, **args):
                result = call(name, **args)
                if name == "inspect_project":
                    result = copy.deepcopy(result)
                    result["project_revision"] = "0" * 64
                return result
            base._call = changed_project
            try:
                stale = host.invoke("read_target", {"function": "m.target"})
                assert stale["bounded_dependencies"]["status"] == "UNKNOWN"
                assert stale["bounded_dependencies"]["reason"] == "CONTEXT_CHANGED_DURING_READ"
            finally:
                base._call = call
            proposal = host.invoke("prepare_change", {"view_id": ready["view_id"], "body": "(body (+ (call helper (ref item)) (int 1)))"})
            assert proposal["status"] == "PREPARED", proposal
            draft = host.invoke("read_target", {"function": "m.target"})
            assert draft["view_state"] == "DRAFT"
            assert draft["bounded_dependencies"]["body_revision"] != context["body_revision"]
            assert draft["bounded_dependencies"]["project_revision"] != context["project_revision"]
            assert sources() == original and not (root / "alva-air/current").exists()
            published = host.invoke("publish_change", {"proposal_id": proposal["proposal_id"]})
            assert published["status"] == "PUBLISHED", published
            assert published["commit"]["host_scope"]["changed_functions"] == ["m.target"]
            assert published["fresh_authority_matches"]
            assert sources() == original
        finally:
            host.close()
        # Existing ContextHost must not opt into this treatment by accident.
        base = MaintenanceHost(lambda: AgentProcess(binary), root / "alva.toml", policy, sources, ReceiptEvaluator())
        old = ContextHost(base)
        try:
            assert "bounded_dependencies" not in old.invoke("read_target", {"function": "m.target"})
        finally:
            old.close()
    print("PASS: real Core context, exact draft read-only/revision binding, actual scope commit/fresh read; evaluator=" + ("Linux isolated" if sdk else "explicit receipt stub (no behavior claim)"))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("binary", type=Path)
    p.add_argument("--toolchain", type=Path)
    p.add_argument("--registry", type=Path)
    a = p.parse_args()
    if bool(a.toolchain) != bool(a.registry):
        p.error("Supply both toolchain and registry for real isolated evaluation")
    sdk = None
    if a.toolchain:
        from integrations.benchmark_runtime_v2.sandbox import SDK
        sdk = SDK(a.binary.resolve(), a.toolchain.resolve(), a.registry.resolve())
    run(a.binary.resolve(), sdk)
