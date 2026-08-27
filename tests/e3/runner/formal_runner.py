#!/usr/bin/env python3
"""E3 FORMAL run runner (execution closure).

PHYSICALLY SEPARATED from rehearsal: this module's execution path never
loads candidate.json, low_sequence, wrong variants, or reference solutions.
It reads ONLY a host-produced run_manifest.json:

  {
    "task_id", "group", "arm", "rep",
    "task_statement",            # injected into the prompt, not the workspace
    "verifier_checkspec",        # host-side, passed arm-blind
    "baseline_revisions",        # host-side, for the untouched gate
    "fixture": "M01",
    "model": {...}               # provider/identifier/settings
  }

Execution path per run:
  1. surface probe in a SEPARATE discarded session (never in trajectory)
  2. FRESH experimental agent (empty call log, no transaction)
  3. model <-> tool relay loop through RecordingAgent
  4. terminal detection -> commit? -> arm-blind hidden verifier
  5. final-state (heads + semantic hash) + reachable revision set
  6. raw artifacts: provenance.json, trajectory.jsonl, verifier.json,
     final-state.json, churn-derived.json

Fails closed unless E3_EXECUTION_AUTHORIZED=1. Without a pinned provider
relay the run is a controlled HOLD; --relay scripted supports the no-model
formal-path rehearsal with a host-side script (deterministic model stub).
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import runner_core as rc  # noqa: E402
from deepseek_relay import DeepSeekRelay  # noqa: E402

AUTH = "E3_EXECUTION_AUTHORIZED"


class ScriptedRelay:
    """Deterministic model stub for the no-model formal-path rehearsal.
    Reads a host-side script: [{"tool": ..., "args": {...}}, {"final": ...}]."""

    def __init__(self, path):
        with open(path, encoding="utf-8") as fh:
            self.steps = json.load(fh)
        self.i = 0

    def step(self, messages):
        if self.i >= len(self.steps):
            return {"type": "final", "text": "(script exhausted)"}
        item = self.steps[self.i]
        self.i += 1
        if "tool" in item:
            return {"type": "tool", "tool": item["tool"],
                    "args": item.get("args", {})}
        return {"type": "final", "text": item.get("final", "")}


class ProviderRelay:
    """Real model relay. The wire protocol is pinned at final readiness;
    until then this raises a controlled HOLD and no model call occurs."""

    def __init__(self, model):
        self.url = os.environ.get("E3_MODEL_RELAY_URL")
        self.model = model
        if not self.url:
            raise RuntimeError("HOLD_MODEL_NOT_CONFIGURED")

    def step(self, messages):
        raise RuntimeError("HOLD_MODEL_RELAY_PROTOCOL_UNPINNED")


def load_tool_defs(arm):
    path = os.path.join(HERE, "tool-schemas",
                        "TOOLS-HIGH.json" if arm == "HIGH"
                        else "TOOLS-LOW.json")
    return json.load(open(path, encoding="utf-8"))["tools"]


def assert_execution_freeze(args, m, alva):
    """Fail-closed identity checks against EXECUTION-FREEZE.json. Any
    mismatch or REQUIRED_INPUT placeholder stops the run before any model
    call (never 'record and continue')."""
    with open(args.execution_freeze, encoding="utf-8") as fh:
        freeze = json.load(fh)
    if args.relay != "scripted":
        for field in ("provider", "model_identifier",
                      "relay_protocol_version", "container_digest"):
            if freeze.get(field) == "REQUIRED_INPUT":
                raise RuntimeError(f"FAIL_CLOSED: {field} not pinned")
        # container-only identity: image digest + in-container binary SHA
        image = freeze["container_digest"]
        insp = subprocess.run(
            ["docker", "image", "inspect", image, "--format",
             "{{.Id}}"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        if insp.returncode != 0:
            raise RuntimeError("FAIL_CLOSED: container image not present")
        sha = subprocess.run(
            ["docker", "run", "--rm", "--entrypoint", "sha256sum", image,
             "/usr/local/bin/alva"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        got = sha.stdout.split()[0].lower() if sha.stdout.strip() else ""
        if got != freeze.get("alva_binary_sha256", "").lower():
            raise RuntimeError("FAIL_CLOSED: in-container alva binary SHA "
                               "mismatch")
        ver = subprocess.run(
            ["docker", "run", "--rm", "--entrypoint", "alva", image,
             "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        if ver.returncode != 0:
            raise RuntimeError("FAIL_CLOSED: in-container alva --version "
                               "failed")
    head = rc._git_head()
    # The checkout must be AT the commit that carries this freeze record,
    # and that commit must descend from the pinned source commit.
    freeze_commit = subprocess.run(
        ["git", "-C", HERE, "log", "-1", "--format=%H", "--",
         os.path.basename(args.execution_freeze)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True).stdout.strip()
    if head != freeze_commit:
        raise RuntimeError(f"FAIL_CLOSED: checkout {head[:12]} != "
                           f"freeze-record commit {freeze_commit[:12]}")
    anc = subprocess.run(
        ["git", "-C", HERE, "merge-base", "--is-ancestor",
         freeze["alva_source_sha"], head],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if anc.returncode != 0:
        raise RuntimeError("FAIL_CLOSED: checkout does not descend from "
                           "pinned alva source")
    if args.relay == "scripted":
        if rc.sha256_file(alva).lower() != \
                freeze.get("rehearsal_host_binary_sha256", "").lower():
            raise RuntimeError("FAIL_CLOSED: host (rehearsal) alva binary "
                               "SHA mismatch")
    runner_hash = (rc.sha256_file(os.path.join(HERE, "runner_core.py")) +
                   rc.sha256_file(os.path.join(HERE, "formal_runner.py")) +
                   rc.sha256_file(os.path.join(HERE, "deepseek_relay.py")))
    if runner_hash.lower() != freeze.get("runner_files_sha256", "").lower():
        raise RuntimeError("FAIL_CLOSED: runner file hash mismatch")
    # per-run manifest identity
    manifest_name = os.path.basename(args.run_manifest)
    index = json.load(open(os.path.join(os.path.dirname(args.run_manifest),
                                        "MANIFEST-INDEX.json"),
                           encoding="utf-8"))
    entry = next((x for x in index["manifests"]
                  if x["manifest"] == manifest_name), None)
    if entry is None:
        raise RuntimeError("FAIL_CLOSED: run manifest not in frozen index")
    live = rc.sha256_file(args.run_manifest)
    if live != entry["sha256"]:
        raise RuntimeError("FAIL_CLOSED: run manifest SHA drifted")
    if rc.sha256_file(os.path.join(os.path.dirname(args.run_manifest),
                                   "MANIFEST-INDEX.json")) != \
            freeze.get("task_manifest_set_hash"):
        raise RuntimeError("FAIL_CLOSED: MANIFEST-INDEX hash drifted")
    return freeze


def run_one(args, m):
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    alva = os.environ["ALVA"]
    freeze = rc.load_freeze_manifest(args.freeze_manifest)
    with open(args.execution_freeze, encoding="utf-8") as fh:
        exfreeze = json.load(fh)
    candidates_dir = os.path.join(os.path.dirname(HERE), "candidates")
    run_root, ws, ws_hash = rc.make_workspace(
        m["fixture"], candidates_dir, freeze, args.out_dir)
    toml = os.path.join(ws, "alva.toml")
    gate_on = m["arm"] == "HIGH"
    # P0-5: surface probe in a SEPARATE discarded session.
    cmd_prefix = None
    agent_project = toml
    verifier_alva = alva
    if args.relay == "deepseek":
        cmd_prefix = rc.container_run_cmd(exfreeze["container_digest"], ws,
                                          gate_on=gate_on)
        agent_project = "/workspace/alva.toml"
        verifier_alva = rc.extract_binary(exfreeze["container_digest"],
                                          run_dir)
    rc.surface_probe(alva, agent_project, gate_on, cmd_prefix=cmd_prefix)
    # FRESH experimental agent: empty call log, no active transaction.
    call_log = []
    agent = rc.RecordingAgent(alva, agent_project, gate_on=gate_on,
                              call_log=call_log, cmd_prefix=cmd_prefix)
    run_dir = os.path.join(args.out_dir, f"RUN-{m['task_id']}-"
                                        f"{m.get('arm')}-r{m.get('rep')}")
    os.makedirs(run_dir, exist_ok=True)
    if args.relay == "scripted":
        relay = ScriptedRelay(args.script)
    else:
        relay = DeepSeekRelay(
            load_tool_defs(m.get("arm", "LOW")),
            os.path.join(args.out_dir, "FINGERPRINT.json"),
            os.path.join(run_dir, "telemetry.jsonl"))
    messages = [{"role": "user", "content": m["task_statement"]}]
    max_steps = m.get("max_tool_steps", 200)
    steps = 0
    final_text = None
    try:
        while True:
            step = relay.step(messages)
            if step["type"] == "final":
                final_text = step.get("text")
                break
            if steps >= max_steps:
                final_text = "(max steps)"
                break
            steps += 1
            call_args = {k: (v.replace("{{project}}", toml)
                             if isinstance(v, str) else v)
                         for k, v in step.get("args", {}).items()}
            if step.get("assistant"):
                messages.append(step["assistant"])
            r = agent.call(step["tool"], **call_args)
            messages.append({
                "role": "tool",
                "tool_call_id": step.get("tool_call_id", ""),
                "content": json.dumps(r),
            })
    except rc.ApiUnreachableError:
        agent.close()
        termination = "API_UNREACHABLE"
        verifier = {"ok": False, "reason": "api unreachable", "output": ""}
        final_rec = {"modules": {}, "base_hash": None}
        reachable = []
        churn_rc, churn_out = rc.derive_churn(call_log, [])
        ended = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        prov = rc.provenance_record(
            m["task_id"], m.get("group"), m.get("arm"), m.get("rep"), alva,
            rc._git_head(), freeze[m["fixture"]][1], ws_hash,
            ("absent" if not gate_on else "1"), m.get("model", {}),
            started, ended, termination, args.out_dir)
        return prov, rc.write_run_artifacts(
            args.out_dir, m["task_id"], m.get("arm"), m.get("rep"), prov,
            call_log, verifier, final_rec, reachable, churn_out)
    except rc.InfraFailureError as e:
        agent.close()
        termination = "INFRA_FAILURE"
        verifier = {"ok": False, "reason": str(e), "output": ""}
        final_rec = {"modules": {}, "base_hash": None}
        reachable = []
        churn_rc, churn_out = rc.derive_churn(call_log, [])
        ended = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        prov = rc.provenance_record(
            m["task_id"], m.get("group"), m.get("arm"), m.get("rep"), alva,
            rc._git_head(), freeze[m["fixture"]][1], ws_hash,
            ("absent" if not gate_on else "1"), m.get("model", {}),
            started, ended, termination, args.out_dir)
        prov["infra_detail"] = str(e)
        return prov, rc.write_run_artifacts(
            args.out_dir, m["task_id"], m.get("arm"), m.get("rep"), prov,
            call_log, verifier, final_rec, reachable, churn_out)
    agent.close()
    # terminal detection + verifier + final state
    commits = [c for c in call_log if c["tool"] == "commit_transaction"]
    if not commits or not commits[-1]["ok"]:
        termination = "NO_COMMIT"
        verifier = {"ok": False, "reason": "no committed store",
                    "output": ""}
        final_rec = {"modules": {}, "base_hash": None}
        reachable = []
    else:
        base = m.get("baseline_revisions")
        passed, out = rc.run_verifier_arm_blind(
            verifier_alva, ws, m["verifier_checkspec"], base)
        verifier = {"ok": passed, "output": out}
        try:
            final_rec = rc.final_state(alva, toml)
            reachable = rc.reachable_revisions(alva, toml)
        except Exception as e:
            final_rec = {"modules": {}, "base_hash": None}
            reachable = []
            verifier = {"ok": False, "output": f"{verifier['output']}\n"
                        f"final-state error: {e}"}
        termination = "OK" if passed else "BAD_SOLUTION"
    churn_rc, churn_out = rc.derive_churn(call_log, reachable)
    ended = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    prov = rc.provenance_record(
        m["task_id"], m.get("group"), m.get("arm"), m.get("rep"), alva,
        rc._git_head(), freeze[m["fixture"]][1], ws_hash,
        ("absent" if not gate_on else "1"), m.get("model", {}),
        started, ended, termination, args.out_dir)
    run_dir = rc.write_run_artifacts(
        args.out_dir, m["task_id"], m.get("arm"), m.get("rep"), prov,
        call_log, verifier, final_rec, reachable, churn_out)
    return prov, run_dir


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-manifest", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--relay", choices=["deepseek", "scripted"],
                    default="deepseek")
    ap.add_argument("--script", default=None,
                    help="scripted relay plan (no-model rehearsal only)")
    ap.add_argument("--freeze-manifest",
                    default=(r"C:\Users\BEStaff\Desktop\alva-repos"
                             r"\alva-research-private\alva-paper\saner"
                             r"\e3-feasibility\C1-FREEZE-MANIFEST.md"))
    ap.add_argument("--execution-freeze",
                    default=os.path.join(HERE, "EXECUTION-FREEZE.json"))
    args = ap.parse_args()
    if os.environ.get(AUTH) != "1":
        sys.exit("FAIL_CLOSED: E3_EXECUTION_AUTHORIZED != 1")
    if args.relay == "scripted" and not args.script:
        sys.exit("--relay scripted requires --script")
    with open(args.run_manifest, encoding="utf-8") as fh:
        m = json.load(fh)
    freeze = assert_execution_freeze(args, m, os.environ["ALVA"])
    blob = json.dumps(m).lower()
    if any(f in blob for f in ("low_sequence", "wrong_variants",
                               "reference solution")):
        sys.exit("FAIL_CLOSED: run manifest contains forbidden solution "
                 "material")
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    try:
        prov, run_dir = run_one(args, m)
    except BaseException as e:  # P1-2: every slot gets exactly one reason
        ended = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        prov = rc.provenance_record(
            m.get("task_id"), m.get("group"), m.get("arm"), m.get("rep"),
            os.environ.get("ALVA", ""), rc._git_head(),
            "unknown", None, ("absent" if m.get("arm") != "HIGH" else "1"),
            m.get("model", {}), started, ended, "RUNNER_CRASH",
            args.out_dir)
        prov["crash_detail"] = f"{type(e).__name__}: {e}"
        os.makedirs(args.out_dir, exist_ok=True)
        with open(os.path.join(args.out_dir, f"RUN-{m.get('task_id')}-"
                                             f"{m.get('arm')}-r"
                                             f"{m.get('rep')}.json"),
                  "w", encoding="utf-8") as fh:
            json.dump(prov, fh, indent=2)
        print(json.dumps(prov, indent=2))
        return 2
    print(json.dumps(prov, indent=2))
    print("artifacts:", run_dir)
    return 0 if prov["termination"] == "OK" else 2


if __name__ == "__main__":
    sys.exit(main())
