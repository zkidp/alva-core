#!/usr/bin/env python3
"""E3 no-model rehearsal runner (deterministic stubs; model connector OFF).

Reads the C1-frozen candidate.json (canonical solutions are allowed in
rehearsal mode ONLY). Per slot:
  MATCHED LOW:   replay frozen LOW canonical sequence
  MATCHED HIGH:  migrate_signature -> check -> commit
  NEUTRAL LOW:   replay frozen LOW canonical sequence
  NEUTRAL HIGH:  replay the SAME LOW canonical sequence with E3 gate ON

Usage:
  ALVA=<alva-exe> python rehearsal_runner.py --out-root <dir>
    [--candidates-dir <dir>] [--freeze-manifest <path>] [--limit N]
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import runner_core as rc  # noqa: E402


def discover_callers(a, inspect_specs):
    callers = []
    for fn, token in inspect_specs:
        insp = a.ok("inspect_function", name=fn)
        body = insp["result"]["body"]
        found = re.findall(
            rf"call name={re.escape(token)} rev=([0-9a-f]{{64}})", body)
        callers.extend(found)
    seen = set()
    return [c for c in callers if not (c in seen or seen.add(c))]


def discover_blocks(a, inspect_blocks):
    blocks = []
    for spec in inspect_blocks or []:
        insp = a.ok("inspect_function", name=spec["fn"])
        m = re.search(r"block rev=([0-9a-f]{64})", insp["result"]["body"])
        if not m:
            raise RuntimeError(f"no block in {spec['fn']}")
        blocks.append(m.group(1))
    return blocks


def discover_calls(a, inspect_calls):
    calls = []
    for spec in inspect_calls or []:
        insp = a.ok("inspect_function", name=spec["fn"])
        calls.extend(re.findall(
            rf"call name={re.escape(spec['call'])} rev=([0-9a-f]{{64}})",
            insp["result"]["body"]))
    return calls


def expand(blob, slots):
    out = blob
    for k, v in slots.items():
        out = out.replace("{{" + k + "}}", v)
    return out


def apply_ops(a, manifest, ops):
    callers = discover_callers(a, manifest.get("inspect", []))
    slots = {}
    for i, b in enumerate(discover_blocks(a,
                                          manifest.get("inspect_blocks", []))):
        slots[f"block{i}"] = b
    for i, c in enumerate(discover_calls(a,
                                         manifest.get("inspect_calls", []))):
        slots[f"call{i}"] = c
    for op in ops:
        args = dict(op.get("args", {}))
        if "{{caller}}" in json.dumps(args):
            subset = callers
            mode = op.get("callers", "all")
            if mode == "first":
                subset = callers[:1]
            elif mode == "none":
                subset = []
            for c in subset:
                concrete = json.loads(expand(json.dumps(args),
                                             dict(slots, caller=c)))
                a.ok(op["tool"], **concrete)
        else:
            concrete = json.loads(expand(json.dumps(args), slots))
            r = a.ok(op["tool"], **concrete)
            if op.get("as"):
                slots[op["as"]] = r["result"].get("revision")


def baseline_revisions(alva, project, functions):
    out = {}
    call_log = []
    a = rc.RecordingAgent(alva, project, gate_on=False, call_log=call_log)
    a.ok("begin_transaction", project=project)
    for fn in functions:
        out[fn] = a.ok("inspect_function", name=fn)["result"]["revision"]
    a.close()
    return out


def run_slot(args, cid, group, arm, rep, manifest, freeze, out_dir, alva):
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    run_root, ws, ws_hash = rc.make_workspace(
        cid, args.candidates_dir, freeze, out_dir)
    toml = os.path.join(ws, "alva.toml")
    call_log = []
    gate_on = (arm == "HIGH")
    # surface gate in a SEPARATE discarded session (never in trajectory)
    rc.surface_probe(alva, toml, gate_on)
    # baseline revisions for the arm-blind verifier
    base = baseline_revisions(alva, toml, manifest.get("functions", []))
    # FRESH experimental agent: empty call log, own transaction
    a = rc.RecordingAgent(alva, toml, gate_on=gate_on, call_log=call_log)
    a.ok("begin_transaction", project=toml)
    # arm route
    if group == "matched" and arm == "HIGH":
        high = rc.extract_high_call(manifest)
        if high is None:
            raise RuntimeError(f"{cid} HIGH: no derived migrate_signature")
        a.ok(high["tool"], **high["args"])
    else:
        apply_ops(a, manifest["low_sequence"], manifest["low_sequence"]["ops"])
    check = a.call("check_transaction")
    commit = a.call("commit_transaction")
    a.close()
    if not check.get("ok"):
        termination = "NO_CHECK_PASS"
    elif not commit.get("ok"):
        termination = "NO_COMMIT"
    else:
        passed, out = rc.run_verifier_arm_blind(
            alva, ws, manifest["verifier"], base)
        termination = "OK" if passed else "BAD_SOLUTION"
    ended = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    reachable = rc.reachable_revisions(alva, toml) if termination in (
        "OK", "BAD_SOLUTION") else []
    churn_rc, churn_out = rc.derive_churn(call_log, reachable)
    rec = rc.provenance_record(
        cid, group, arm, rep, alva, _head(), freeze[cid][1], ws_hash,
        ("absent" if not gate_on else "1"),
        {"provider": None, "identifier": None, "settings": None,
         "image": None},
        started, ended, termination, out_dir)
    return rec, call_log, churn_out


def _head():
    try:
        p = subprocess.run(["git", "rev-parse", "HEAD"],
                           capture_output=True, text=True,
                           cwd=os.path.dirname(os.path.dirname(HERE)))
        return p.stdout.strip()
    except Exception:
        return "unknown"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-root", required=True)
    ap.add_argument("--candidates-dir",
                    default=os.path.join(os.path.dirname(HERE),
                                         "candidates"))
    ap.add_argument("--freeze-manifest",
                    default=(r"C:\Users\BEStaff\Desktop\alva-repos"
                             r"\alva-research-private\alva-paper\saner"
                             r"\e3-feasibility\C1-FREEZE-MANIFEST.md"))
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    alva = os.environ.get("ALVA")
    if not alva:
        sys.exit("set ALVA to the alva executable")
    freeze = rc.load_freeze_manifest(args.freeze_manifest)
    os.makedirs(args.out_root, exist_ok=True)
    results, slots = [], []
    for cid in sorted(freeze):
        m = json.load(open(os.path.join(args.candidates_dir, cid,
                                        "candidate.json"), encoding="utf-8"))
        group = m["group"]
        for arm in ("LOW", "HIGH"):
            for rep in (1, 2):
                slots.append((cid, group, arm, rep, m))
    if args.limit:
        slots = slots[:args.limit]
    for cid, group, arm, rep, m in slots:
        rec, log, churn = run_slot(args, cid, group, arm, rep, m, freeze,
                                   args.out_root, alva)
        results.append(rec)
        print(f"{cid} {group} {arm} r{rep}: {rec['termination']}",
              flush=True)
    ok = sum(1 for r in results if r["termination"] == "OK")
    with open(os.path.join(args.out_root, "REHEARSAL-MANIFEST.json"),
              "w", encoding="utf-8") as fh:
        json.dump({"slots": results, "ok": ok, "total": len(results)}, fh,
                  indent=2)
    print(f"REHEARSAL: {ok}/{len(results)} slots OK")
    return 0 if ok == len(results) and results else 1


if __name__ == "__main__":
    sys.exit(main())
