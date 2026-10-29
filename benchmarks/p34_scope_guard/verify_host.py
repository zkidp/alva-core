"""Four fixed cases through real AppServer approval + scripted Responses.

No upstream provider, no credentials, no actual model. Existing P31 transport
fixture and P26 service ownership reused; no Core/Skill/historical file edits.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time
import zipfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from benchmarks.native_prospective import pilot as old
from benchmarks.maintenance_design import witnesses
from benchmarks.maintenance_design.feasibility import Client
from benchmarks.p34_scope_guard.cases import CASES, TOOLS, case
from integrations.benchmark_runtime_v2.freeze import sha, canonical

spec = importlib.util.spec_from_file_location("p34_p31_probe", ROOT / "tests/integrations/native_commit_authorization_test.py")
p31 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p31)
HERE = Path(__file__).resolve().parent


class Slot(old.Slot):
    def __init__(self, runtime, entry, unused, args, fixed):
        self.path = runtime / entry["id"]
        self.path.mkdir(parents=True, exist_ok=False)
        self.service = HERE / "service.py"
        self.ready, self.evidence = self.path / "ready.json", self.path / "linux.json"
        self.config = {"bundle": fixed["bundle"], "case": fixed["id"], "arm": "N", "vectors": [], "docs": {},
            "ready": old.linux(self.ready), "evidence": old.linux(self.evidence),
            "guard_evidence": old.linux(self.path / "guard.jsonl"),
            "alva": args.alva, "toolchain": args.toolchain, "registry": args.registry}
        old.save(self.path / "config.json", self.config)
        self.process = subprocess.Popen(["wsl.exe", "-d", "Ubuntu-26.04", "--exec", "python3", old.linux(self.service),
            "--role", "server", "--config", old.linux(self.path / "config.json")], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        deadline = time.monotonic() + 30
        while not self.ready.exists():
            if self.process.poll() is not None:
                raise RuntimeError("SERVICE_EXIT:" + self.process.communicate()[1].decode(errors="replace")[-2000:])
            if time.monotonic() >= deadline:
                self.process.kill(); self.process.communicate()
                raise RuntimeError("SERVICE_TIMEOUT")
            time.sleep(.05)


class ActionClient(Client):
    def __init__(self, probe):
        super().__init__(None, [])
        self.probe = probe

    def raw(self, operation, **args):
        arguments = args if operation == "begin_transaction" else {"transaction_id": self.tx, **args}
        item = self.probe.action(operation, arguments)
        if item.get("error"):
            raise RuntimeError("APPSERVER_ERROR:" + json.dumps(item["error"]))
        # AppServer reports MCP isError as item.status, not as a retained
        # isError member in its normalized result envelope.
        return dict(item["result"], isError=item["status"] == "failed")


def main(args):
    path = ROOT / ".local/p34-scope-guard" / args.attempt
    path.mkdir(parents=True, exist_ok=False)
    rows = []
    for name in CASES:
        print("P34 " + name, flush=True)
        fixed = case(name)
        factory = lambda runtime, entry, frozen, config: Slot(runtime, entry, frozen, config, fixed)
        # Reuse P31's empty-home loopback provider, strict P31 scoped approval,
        # real model-tool routing, event collection and confirmed turn terminal.
        with patch.object(p31.old, "Slot", factory), patch.object(p31, "ALLOWED", list(TOOLS)):
            probe = p31.Probe(args, path / name)
        try:
            assert probe.thread["modelProvider"] == "p31_synthetic"
            inventory = next(s["tools"] for s in probe.inventory["data"] if s["name"] == "alva")
            assert set(inventory) == set(TOOLS)
            assert inventory["commit_transaction"]["annotations"]["destructiveHint"] is True
            policy = probe.config_read["config"]
            assert set(policy["mcp_servers"]) == {"alva"}
            assert policy["mcp_servers"]["alva"]["tools"] == {"commit_transaction": {"approval_mode": "approve"}}
            assert policy["approval_policy"] == "never" and probe.thread["sandbox"]["type"] == "readOnly"
            c = ActionClient(probe)
            c.begin()
            before = c.bodies(fixed["task"]["functions"])
            original = probe.snapshot()
            attachment = witnesses.mutate_native(fixed["task"]["id"], c)
            staged = c.bodies(fixed["task"]["functions"])
            changed = [n for n in before if before[n] != staged[n]]
            preview = c.call("preview_semantic_diff")
            check = c.call("check_transaction")
            assert check == {"problems": []}
            assert probe.snapshot() == original
            commit_item = probe.action("commit_transaction", {"transaction_id": c.tx})
            assert not commit_item.get("error"), commit_item
            decision = commit_item["result"]["structuredContent"]["host_scope"]
            assert decision["status"] == fixed["expected_scope"], decision
            published = probe.snapshot()
            allowed = decision["status"] == "SCOPE_ALLOWED"
            if allowed:
                assert commit_item["status"] == "completed"
                assert published != original and "alva-air/current" in published
            else:
                assert commit_item["status"] == "failed" and published == original
                c.call("abort_transaction")
            # The model channel has no second/raw server, policy-update tool,
            # shell/web access or candidate write path around this mediator.
            output = probe.script('try { await tools.mcp__raw_alva__commit_transaction({transaction_id:"x"}); text("BYPASS"); } catch(e) { text("NO_RAW_COMMIT_ENDPOINT"); }')
            assert "NO_RAW_COMMIT_ENDPOINT" in json.dumps(output)
            row = {"id": name, "authorized_functions": fixed["policy"]["authorized_functions"],
                "attachment": attachment, "changed_functions": changed, "preview": preview, "check_transaction": check,
                "scope_decision": decision, "authority_unchanged_when_denied": not allowed and published == original,
                "commit_appserver_call_id": commit_item["id"], "model_tool_approval_error": commit_item.get("error"),
                "raw_commit_endpoint_unavailable": True, "model_generation_calls": 0}
        finally:
            evidence = probe.close()
        assert evidence["status"] == "CLOSED" and not evidence.get("error") and not evidence.get("worker_error")
        ledger = [json.loads(line) for line in (probe.slot.path / "guard.jsonl").read_text().splitlines()]
        actual = [e for e in ledger if e["event"] == "native_dispatch" and e.get("params", {}).get("name") == "commit_transaction"]
        denied = [e for e in ledger if e["event"] == "scope_denied_no_native_dispatch" and e.get("params", {}).get("name") == "commit_transaction"]
        assert len(actual) == int(allowed) and len(denied) == int(not allowed)
        if actual:
            assert actual[0]["origin"] == "guarded_commit"
            assert actual[0]["params"]["_meta"]["callId"] == row["commit_appserver_call_id"]
        event = actual[0] if actual else denied[0]
        session = event["scope_session_id"]
        own = [e for e in ledger if e["scope_session_id"] == session]
        baselines = [(i, e) for i, e in enumerate(own) if e["event"] == "trusted_baseline"]
        assert len(baselines) == 1
        mutations = [i for i, e in enumerate(own) if e["event"] == "native_dispatch" and e.get("params", {}).get("name") in
            {"create_literal", "create_binary", "create_if", "create_reference", "replace_expression", "change_field"}]
        assert mutations and baselines[0][0] < min(mutations)
        final = evidence["final"]
        assert final["regression"]["status"] == "PASS"
        assert final["goal"]["status"] == ("PASS" if allowed else "TEST_FAIL")
        if not allowed:
            assert evidence["initial_authority"] == evidence["final_authority"]
        else:
            commit_revision = actual[0]["response"]["structuredContent"]["revision"]
            assert evidence["final_authority"]["project_revision"] == commit_revision
            assert [n for n in before if before[n] != evidence["final_authority"]["bodies"][n]] == [fixed["task"]["target"]]
        row.update(native_commit_dispatches=len(actual), denied_commits=len(denied),
            baseline_attempted_before_mutation=True, baseline_valid="error" not in baselines[0][1]["snapshot"],
            initial_authority=evidence["initial_authority"], final_authority=evidence["final_authority"],
            fresh_process_authority_reread=True, independent_task=final["goal"]["status"],
            independent_regression=final["regression"]["status"],
            source_projection_unchanged=all(published[p] == original[p] for p in original),
            guard_evidence_sha256=sha((probe.slot.path / "guard.jsonl").read_bytes()),
            native_evidence_sha256=sha(probe.slot.evidence.read_bytes()))
        rows.append(row)
        old.save(path / "progress.json", rows)
    names = ["integrations/codex/precommit_scope_guard.py", "integrations/codex/native_commit_authorization.py",
        "tests/integrations/native_commit_authorization_test.py", "tests/integrations/p31_synthetic_provider.py",
        "benchmarks/native_prospective/pilot.py", "benchmarks/native_prospective/service.py",
        "integrations/benchmark_runtime_v2/persistent.py", "integrations/benchmark_runtime_v2/sandbox.py",
        "benchmarks/maintenance_design/TASK-CANDIDATES.json", "benchmarks/maintenance_design/witnesses.py"]
    names += [p.relative_to(ROOT).as_posix() for p in HERE.glob("*.py")]
    summary = {"status": "PASS", "base": "46f5398c0ea591674df6f1c9604a0c983af426bc",
        "model_generation_calls": 0, "input_token_api_calls": 0,
        "model_approval_path": "REAL_APPSERVER_SYNTHETIC_RESPONSES_NO_MODEL",
        "codex": subprocess.check_output([p31.shutil.which("codex"), "--version"], text=True).strip(),
        "codex_binary_sha256": sha(Path(p31.shutil.which("codex")).read_bytes()),
        "sdk_identity": old.sdk_identity(args),
        "executed_file_sha256": {n: sha((ROOT / n).read_bytes()) for n in sorted(set(names))},
        "rows": rows, "native_commit_dispatches": sum(r["native_commit_dispatches"] for r in rows),
        "denied_commits": sum(r["denied_commits"] for r in rows)}
    old.save(path / "RESULTS.json", summary)
    archive = path / "RAW.zip"
    with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED) as z:
        for file in sorted(path.rglob("*")):
            if file.is_file() and file != archive:
                assert file.name not in {"auth.json", "config.toml"}
                z.write(file, file.relative_to(path).as_posix())
    old.save(path / "ARCHIVE.json", {"sha256": sha(archive.read_bytes()), "bytes": archive.stat().st_size,
        "controlled_local_only": True, "contains_credentials": False})
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--attempt", required=True)
    for k in ("alva", "toolchain", "registry"):
        p.add_argument("--" + k, required=True)
    main(p.parse_args())
