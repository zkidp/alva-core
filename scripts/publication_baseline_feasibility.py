"""Deterministic publication-boundary exercise, not a model benchmark or Guard.

Uses the public PR43 fixture and existing Host/evaluator. Git plumbing below is
a small trusted test driver, NOT an agent-facing server or production gate.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.maintenance_consumer_walkthrough import (
    SAMPLE, INPUTS, POLICY, CORRECT, WRONG, Client, source_files, save_files,
    authority_files, projected_sources,
)
from integrations.benchmark_runtime_v2.sandbox import SDK, LinuxSandbox
from integrations.codex.maintenance_evaluator import LinuxProjectEvaluator
from integrations.codex.maintenance_host import snapshot_digest, sha

BASE_BODY = b"(body (/ (ref units) (ref pack_size)))"
CASES = ("correct", "malformed", "behavior_wrong", "failed_reprepare",
         "source_changed", "authority_changed")
BAD = "(body (int ))"
ALTERNATE = "(body (+ " + CORRECT[len("(body "):-1] + " (int 0)))"
REF = "refs/heads/published"


def candidate_source(base, body):
    result = dict(base)
    if base["src/model.alva"].count(BASE_BODY) != 1:
        raise RuntimeError("FIXTURE_BODY_NOT_UNIQUE")
    result["src/model.alva"] = base["src/model.alva"].replace(BASE_BODY, body.encode())
    return result


def allowed_source_change(base, candidate):
    """Trusted byte-region allowance for this exact example, not an ALVA parser."""
    if set(base) != set(candidate) or base["src/model.alva"].count(BASE_BODY) != 1:
        return False
    if any(base[p] != candidate[p] for p in base if p != "src/model.alva"):
        return False
    prefix, suffix = base["src/model.alva"].split(BASE_BODY)
    data = candidate["src/model.alva"]
    return len(data) > len(prefix) + len(suffix) and data.startswith(prefix) and data.endswith(suffix)


class GitPublication:
    """Disposable real Git immutable objects + checked old-ref publication.

    Caller is trusted; only the fixed example input paths are accepted. No shell,
    candidate hook, checkout, shared user config, remote or push is involved.
    """
    def __init__(self, root, base):
        root.mkdir()
        self.root, self.base = root, dict(base)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        empty_config = root / "empty-config"
        empty_config.write_bytes(b"")
        template = root / "empty-template"
        template.mkdir()
        self.env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=str(empty_config),
                        GIT_TEMPLATE_DIR=str(template), GIT_AUTHOR_NAME="Public fixture",
                        GIT_AUTHOR_EMAIL="fixture@example.invalid", GIT_COMMITTER_NAME="Public fixture",
                        GIT_COMMITTER_EMAIL="fixture@example.invalid", GIT_AUTHOR_DATE="2026-01-01T00:00:00Z",
                        GIT_COMMITTER_DATE="2026-01-01T00:00:00Z")
        self.calls, self.proposal = [], None
        self.run("init", "--bare", "--object-format=sha1", str(root / "repo.git"))
        self.base_oid = self.object(base)
        self.run("update-ref", REF, self.base_oid, "0" * 40)

    def run(self, *args, data=None, check=True):
        p = subprocess.run(["git", "--git-dir", str(self.root / "repo.git"), *args],
                           input=data, capture_output=True, env=self.env, timeout=30)
        self.calls.append({"args": list(args), "exit": p.returncode,
                           "stdout": p.stdout.decode(errors="replace"),
                           "stderr": p.stderr.decode(errors="replace")})
        if check and p.returncode:
            raise RuntimeError("GIT_TEST_DRIVER_FAILURE:" + p.stderr.decode(errors="replace")[:500])
        return p

    def object(self, files):
        if set(files) != set(INPUTS):
            raise ValueError("Only fixed public source input paths supported")
        blobs = {p: self.run("hash-object", "-w", "--stdin", data=b).stdout.strip().decode()
                 for p, b in sorted(files.items())}
        def tree(prefix=""):
            entries = []
            children = sorted({p[len(prefix):].split("/")[0] for p in blobs if p.startswith(prefix)})
            for child in children:
                path = prefix + child
                if path in blobs:
                    entries.append(f"100644 blob {blobs[path]}\t{child}\n")
                else:
                    entries.append(f"040000 tree {tree(path + '/')}\t{child}\n")
            return self.run("mktree", data="".join(entries).encode()).stdout.strip().decode()
        args = ["commit-tree", tree()]
        if hasattr(self, "base_oid"):
            args += ["-p", self.base_oid]
        return self.run(*args, data=b"Public deterministic candidate\n").stdout.strip().decode()

    def files(self, oid):
        names = self.run("ls-tree", "-r", "--name-only", oid).stdout.decode().splitlines()
        if set(names) != set(INPUTS):
            raise RuntimeError("GIT_TREE_INPUT_MISMATCH")
        return {p: self.run("show", oid + ":" + p).stdout for p in names}

    def current(self):
        return self.run("rev-parse", REF).stdout.strip().decode()

    def prepare(self, candidate, evaluate):
        self.proposal = None  # Explicit trusted-pipeline rule, not a built-in Git policy.
        if not allowed_source_change(self.base, candidate):
            return {"status": "REJECTED", "reason": "SOURCE_SCOPE_VIOLATION"}
        oid = self.object(candidate)
        exact = self.files(oid)  # Evaluate immutable Git bytes, not a mutable worktree.
        result = evaluate(exact)
        if result["status"] != "PASS":
            return {"status": "VALIDATION_FAILED", "checks": result["checks"]}
        self.proposal = {"oid": oid, "snapshot_sha256": snapshot_digest(exact), "evaluation": result}
        return {"status": "PREPARED", "checks": result["checks"], "oid": oid}

    def publish(self, live_source):
        proposal, self.proposal = self.proposal, None
        if not proposal:
            return {"status": "REJECTED", "reason": "NO_CURRENT_PREPARATION"}
        if snapshot_digest(live_source) != snapshot_digest(self.base):
            return {"status": "REJECTED", "reason": "SOURCE_BASE_CHANGED"}
        exact = self.files(proposal["oid"])
        if snapshot_digest(exact) != proposal["snapshot_sha256"]:
            raise RuntimeError("CHECKED_GIT_BYTES_MISMATCH")
        p = self.run("update-ref", REF, proposal["oid"], self.base_oid, check=False)
        if p.returncode:
            return {"status": "REJECTED", "reason": "REF_UPDATE_FAILED",
                    "stale_base_confirmed": self.current() != self.base_oid}
        if self.current() != proposal["oid"]:
            raise RuntimeError("PUBLISHED_GIT_REF_MISMATCH")
        return {"status": "PUBLISHED", "oid": proposal["oid"],
                "snapshot_sha256": snapshot_digest(self.files(proposal["oid"]))}


def source_evaluation(sdk, evaluator, snapshot):
    # Invalid source must get an ordinary compiler result, not a host parse exception.
    driver = r'''
import json,subprocess
p=subprocess.run(['/sdk/alva','project','check','alva.toml','--json'],capture_output=True,text=True)
result={'checks':{'check':'FAIL','build':'NOT_RUN','test':'NOT_RUN'},'diagnostic':p.stdout[-4000:]+p.stderr[-4000:]}
if p.returncode==0:
 requests=[{'tool':'begin_transaction','project':'alva.toml','request_id':'read'}, {'tool':'abort_transaction','request_id':'abort'}]
 r=subprocess.run(['/sdk/alva','agent'],input='\n'.join(json.dumps(x) for x in requests)+'\n',capture_output=True,text=True,check=True)
 first=json.loads(r.stdout.splitlines()[0])
 if not first.get('ok'):raise RuntimeError('SOURCE_REVISION_READ_FAILED')
 result={'revision':first['result']['project_revision']}
print(json.dumps(result))
'''
    run = LinuxSandbox(sdk).run(snapshot, ["/usr/bin/python3", "-I", "-c", driver])
    if run["status"] != "EXECUTED" or run["exit"] != 0:
        raise RuntimeError("ISOLATED_SOURCE_CHECK_FAILURE")
    result = json.loads(run["stdout"]["text"])
    if "revision" not in result:
        return dict(result, status="FAIL")
    return evaluator(snapshot, result["revision"])


def native_project(root, sdk, assertions):
    project, operator = root / "project", root / "operator"
    operator.mkdir(parents=True)
    original = {p: (SAMPLE / p).read_bytes() for p in INPUTS}
    save_files(project, original)
    config = {"alva": str(sdk.alva), "toolchain": str(sdk.rust_toolchain), "registry": str(sdk.registry),
              "project": str(project / "alva.toml"), "inputs": list(INPUTS), "crate": "packing_demo",
              "assertions": assertions, "policy": POLICY}
    config_path = operator / "host.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    client = Client(config_path, operator)
    client.request("initialize")
    return client, project, operator


def native_case(root, sdk, evaluator, assertions, case):
    client, project, operator = native_project(root, sdk, assertions)
    second = None
    original = source_files(project)
    events = []
    try:
        def tool(name, args):
            value = client.tool(name, args)
            events.append({"tool": name, "result": value})
            return value
        view = tool("read_target", {"function": "model.packs_required"})
        if view["status"] != "READY":
            raise RuntimeError("NATIVE_VIEW_NOT_READY")
        body = BAD if case == "malformed" else WRONG if case == "behavior_wrong" else CORRECT
        prepared = tool("prepare_change", {"view_id": view["view_id"], "body": body})
        proposal_id = prepared.get("proposal_id", "no-proposal")
        if case == "failed_reprepare":
            tool("prepare_change", {"view_id": view["view_id"], "body": BAD})
        if case == "source_changed":
            (project / "src/app.alva").write_bytes(original["src/app.alva"] + b"\n")
        if case == "authority_changed":
            # Real second Host, same public authorization/tests, no unguarded commit.
            second_operator = operator / "concurrent-client"
            second_operator.mkdir()
            second = Client(operator / "host.json", second_operator)
            second.request("initialize")
            v = second.tool("read_target", {"function": "model.packs_required"})
            p = second.tool("prepare_change", {"view_id": v["view_id"], "body": ALTERNATE})
            if p["status"] != "PREPARED": raise RuntimeError("CONCURRENT_PREPARE_FAILED")
            c = second.tool("publish_change", {"proposal_id": p["proposal_id"]})
            if c["status"] != "PUBLISHED": raise RuntimeError("CONCURRENT_PUBLICATION_FAILED")
            concurrent = authority_files(project)[0]
            (operator / "concurrent-calls.json").write_text(json.dumps(second.events, indent=2), encoding="utf-8")
            second.close()
            second = None
        publication = tool("publish_change", {"proposal_id": proposal_id})
        after = authority_files(project) if (project / "alva-air/current").exists() else None
        preserved = case != "authority_changed" or after[0] == concurrent
        final_evaluation = None
        source_handoff = False
        if after:
            final_snapshot = {**source_files(project), **after[0]}
            final_evaluation = evaluator(final_snapshot, after[1])
            if publication["status"] == "PUBLISHED":
                projected = projected_sources(sdk, final_snapshot, after[2])
                # Source-only independent evaluator reads its revision inside isolation.
                projected_result = source_evaluation(sdk, evaluator, projected)
                source_handoff = projected_result["status"] == "PASS"
                save_files(root / "handoff-source", projected)
        return {"prepare": prepared, "publication": publication, "events": events,
                "authoritative_state": "PUBLISHED_AIR" if after else "ORIGINAL_SOURCE",
                "source_files_unchanged": source_files(project) == original,
                "concurrent_state_preserved": preserved, "source_handoff_verified": source_handoff,
                "final_evaluation": final_evaluation, "stdio_requests": len(client.events)}
    finally:
        if second: second.close()
        client.close()
        (operator / "calls.json").write_text(json.dumps(client.events, indent=2), encoding="utf-8")


def run(sdk, output):
    LinuxSandbox(sdk)  # Fail closed before making output or a Git publication repository.
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    base = {p: (SAMPLE / p).read_bytes() for p in INPUTS}
    assertions = (SAMPLE / "operator/checks.rs").read_text(encoding="utf-8")
    evaluator = LinuxProjectEvaluator(sdk, "packing_demo", assertions=assertions)
    report = {"status": "RUNNING", "classification": "DETERMINISTIC_FEASIBILITY_NOT_USER_VALUE_STUDY",
              "model_generation_calls": 0, "token_api_calls": 0, "pairs": [],
              "input_sha256": snapshot_digest(base), "evaluator_identity": evaluator.identity(),
              "driver_sha256": sha(Path(__file__).read_bytes()), "git_version": subprocess.check_output(["git", "--version"]).decode().strip()}
    (output / "INPUTS.json").write_text(json.dumps({
        "cases": list(CASES), "base_sha256": snapshot_digest(base), "policy": POLICY,
        "assertions_sha256": sha(assertions.encode()), "driver_sha256": report["driver_sha256"],
        "expected_publication": {case: case == "correct" for case in CASES},
        "not_a_model_input_freeze": True}, indent=2), encoding="utf-8")
    try:
        for case in CASES:
            start = time.monotonic()
            root = output / case
            root.mkdir()
            git = GitPublication(root / "git", base)
            evaluate = lambda files: source_evaluation(sdk, evaluator, files)
            body = BAD if case == "malformed" else WRONG if case == "behavior_wrong" else CORRECT
            prepared = git.prepare(candidate_source(base, body), evaluate)
            if case == "failed_reprepare": git.prepare(candidate_source(base, BAD), evaluate)
            live = dict(base)
            if case == "source_changed": live["src/app.alva"] += b"\n"
            if case == "authority_changed":
                concurrent = git.object(candidate_source(base, ALTERNATE))
                concurrent_result = evaluate(git.files(concurrent))
                if concurrent_result["status"] != "PASS": raise RuntimeError("GIT_CONCURRENT_CHECK_FAILED")
                git.run("update-ref", REF, concurrent, git.base_oid)
            publication = git.publish(live)
            published = git.files(git.current())
            final = evaluate(published)
            save_files(root / "git-handoff", published)
            text = {"prepare": prepared, "publication": publication, "final_evaluation": final,
                    "concurrent_state_preserved": case != "authority_changed" or git.current() == concurrent,
                    "git_commands": len(git.calls), "published_oid": git.current(),
                    "published_snapshot_sha256": snapshot_digest(published)}
            (root / "git-commands.json").write_text(json.dumps(git.calls, indent=2), encoding="utf-8")
            native = native_case(root / "native", sdk, evaluator, assertions, case)
            expected = case == "correct"
            for side in (text, native):
                if (side["publication"]["status"] == "PUBLISHED") != expected:
                    raise RuntimeError("UNEXPECTED_PUBLICATION:" + case)
                if not side["concurrent_state_preserved"]:
                    raise RuntimeError("CONCURRENT_STATE_LOST")
            if text["final_evaluation"]["status"] != ("PASS" if case in ("correct", "authority_changed") else "FAIL"):
                raise RuntimeError("UNEXPECTED_FINAL_TEXT_BEHAVIOR")
            if expected and (native["final_evaluation"]["status"] != "PASS" or not native["source_handoff_verified"]):
                raise RuntimeError("NATIVE_HANDOFF_FAILURE")
            report["pairs"].append({"case": case, "text_git_tests": text, "alva_host": native,
                                    "combined_elapsed_seconds_not_comparative_cost": round(time.monotonic() - start, 3)})
        # Separate interface-coverage probe: a source edit can touch a protected helper;
        # the three-action Host accepts one authorized body, not a whole source proposal.
        neighbor = candidate_source(base, CORRECT)
        neighbor["src/model.alva"] = neighbor["src/model.alva"].replace(
            b"(body (* (/ (ref units) (ref pack_size)) (ref pack_size)))",
            b"(body (+ (* (/ (ref units) (ref pack_size)) (ref pack_size)) (int 0))))")
        checked = source_evaluation(sdk, evaluator, neighbor)
        allowed = allowed_source_change(base, neighbor)
        if allowed or checked["status"] != "PASS": raise RuntimeError("NEIGHBOR_PROBE_MISMATCH")
        report["unpaired_scope_probe"] = {"checks": checked["checks"], "text_byte_scope_allowed": allowed,
            "native": "NOT_REPRESENTABLE_BY_THREE_ACTION_INPUT", "not_a_native_rejection_measurement": True}
        report.update(status="PASS", decision="NO_INCREMENTAL_SAFETY_DECISION_OBSERVED_IN_THIS_FIXTURE",
                      structured_competitor="NOT_EXECUTED_NO_OFF_THE_SHELF_ALVA_ADAPTER_ESTABLISHED",
                      human_walkthrough="NOT_EXECUTED_PARTICIPANT_UNAVAILABLE")
    except Exception as exc:
        report.update(status="FAIL", error=type(exc).__name__ + ":" + str(exc)[:2000])
        raise
    finally:
        (output / "RESULTS.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("alva", "toolchain", "registry", "output"):
        parser.add_argument("--" + key, type=Path, required=True)
    args = parser.parse_args()
    result = run(SDK(args.alva.resolve(), args.toolchain.resolve(), args.registry.resolve()), args.output)
    print(json.dumps({"status": result["status"], "decision": result["decision"], "pairs": len(result["pairs"])}, indent=2))
