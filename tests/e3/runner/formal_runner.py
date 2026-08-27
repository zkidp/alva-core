#!/usr/bin/env python3
"""E3 FORMAL run runner.

PHYSICALLY SEPARATED from rehearsal: this module's execution path never
loads candidate.json, low_sequence, wrong variants, or reference solutions.
It reads ONLY a host-produced run_manifest.json:

  {
    "task_id", "group", "arm", "rep",
    "task_statement",            # injected into the prompt, not the workspace
    "verifier_checkspec",        # host-side, passed arm-blind
    "baseline_revisions",        # host-side, for the untouched gate
    "fixture": "M01",
    "model": {...}               # provider/identifier/settings (env or file)
  }

Fails closed unless E3_EXECUTION_AUTHORIZED=1. Model relay must be
configured (E3_MODEL_RELAY_URL etc.); otherwise the run is a controlled
HOLD (HOLD_MODEL_NOT_CONFIGURED), never a silent local run.
"""

import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import runner_core as rc  # noqa: E402

AUTH = "E3_EXECUTION_AUTHORIZED"


class ModelRelay:
    """Formal-mode model connector. Rehearsal never constructs this."""

    def __init__(self, model):
        self.url = os.environ.get("E3_MODEL_RELAY_URL")
        self.model = model
        if not self.url:
            raise RuntimeError("HOLD_MODEL_NOT_CONFIGURED")

    def complete(self, messages):
        # The actual relay protocol is pinned at final readiness review;
        # until then this raises so no formal run can silently proceed.
        raise RuntimeError("HOLD_MODEL_RELAY_PROTOCOL_UNPINNED")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-manifest", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--freeze-manifest",
                    default=(r"C:\Users\BEStaff\Desktop\alva-repos"
                             r"\alva-research-private\alva-paper\saner"
                             r"\e3-feasibility\C1-FREEZE-MANIFEST.md"))
    args = ap.parse_args()
    alva = os.environ.get("ALVA")
    if not alva:
        sys.exit("set ALVA to the alva executable")
    if os.environ.get(AUTH) != "1":
        sys.exit("FAIL_CLOSED: E3_EXECUTION_AUTHORIZED != 1")
    with open(args.run_manifest, encoding="utf-8") as fh:
        m = json.load(fh)
    # structural guard: formal execution path must not touch solutions
    forbidden = ("low_sequence", "wrong_variants", "reference", "solution")
    blob = json.dumps(m).lower()
    if any(f in blob for f in forbidden):
        sys.exit("FAIL_CLOSED: run manifest contains forbidden solution "
                 "material")
    freeze = rc.load_freeze_manifest(args.freeze_manifest)
    candidates_dir = os.path.join(os.path.dirname(HERE), "candidates")
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    ws_hash = None
    try:
        run_root, ws, ws_hash = rc.make_workspace(
            m["fixture"], candidates_dir, freeze, args.out_dir)
        toml = os.path.join(ws, "alva.toml")
        gate_on = m["arm"] == "HIGH"
        call_log = []
        a = rc.RecordingAgent(alva, toml, gate_on=gate_on,
                              call_log=call_log)
        rc.surface_probe(a, toml)
        relay = ModelRelay(m.get("model", {}))
        # Prompt: task_statement only; workspace is allowlist-only.
        prompt = [{"role": "user",
                   "content": m["task_statement"]}]
        response = relay.complete(prompt)
        # The agent session consumes the model trajectory; per-call facts
        # are recorded by RecordingAgent. Response pinned into provenance.
        termination = "OK"
    except RuntimeError as e:
        termination = str(e)
        run_root = ws = None
    ended = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    rec = rc.provenance_record(
        m.get("task_id"), m.get("group"), m.get("arm"), m.get("rep"), alva,
        rc._git_head(), freeze[m["fixture"]][1],
        ws_hash, ("absent" if not gate_on else "1"),
        m.get("model", {}), started, ended, termination, args.out_dir)
    os.makedirs(args.out_dir, exist_ok=True)
    with open(os.path.join(args.out_dir, f"RUN-{m['task_id']}-"
                                         f"{m['arm']}-r{m['rep']}.json"),
              "w", encoding="utf-8") as fh:
        json.dump(rec, fh, indent=2)
    print(json.dumps(rec, indent=2))
    return 0 if termination == "OK" else 2


if __name__ == "__main__":
    sys.exit(main())
