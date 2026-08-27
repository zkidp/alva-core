#!/usr/bin/env python3
"""Zero-model qualification harness for E3 candidates (C1).

Per candidate directory (fixture/ + candidate.json):
  1. baseline `alva project check` on the pristine fixture;
  2. reference: the deterministic LOW canonical sequence (from
     candidate.json "low_sequence") -> check -> commit -> hidden verifier
     must PASS;
  3. each wrong variant (candidate.json "wrong_variants"): fresh fixture,
     variant ops -> commit -> hidden verifier must FAIL.

No model calls anywhere. LLM difficulty probes are forbidden by policy.

Usage: ALVA=<alva-exe> python qualify_candidate.py <candidate-dir>...
Exit: 0 = all candidates qualified; 1 = any failure.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
VERIFIER = os.path.join(HERE, "hidden_verifier.py")


def fail(msg):
    print(f"QUALIFY FAIL: {msg}", flush=True)
    raise SystemExit(1)


def log(msg):
    print(msg, flush=True)


class Agent:
    def __init__(self, alva, project):
        env = dict(os.environ)
        env.setdefault("ALVA_AEP_ENABLE_EXPERIMENTAL_A1", "1")
        self.p = subprocess.Popen(
            [alva, "agent"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            text=True, encoding="utf-8", env=env,
        )
        self.project = project
        self.i = 0

    def call(self, tool, **kw):
        self.i += 1
        msg = {"request_id": str(self.i), "tool": tool}
        msg.update(kw)
        self.p.stdin.write(json.dumps(msg) + "\n")
        self.p.stdin.flush()
        line = self.p.stdout.readline()
        if not line.strip():
            raise RuntimeError("agent process closed")
        return json.loads(line)

    def ok(self, tool, **kw):
        r = self.call(tool, **kw)
        if not r.get("ok"):
            fail(f"{tool} {kw} -> {r.get('message')}")
        return r

    def close(self):
        self.p.stdin.close()
        self.p.wait()


def fresh_copy(fixture_dir):
    work = tempfile.mkdtemp(prefix="cand-")
    proj_dir = os.path.join(work, "proj")
    shutil.copytree(fixture_dir, proj_dir)
    return os.path.join(proj_dir, "alva.toml")


def discover_callers(a, inspect_specs):
    callers = []
    for fn, token in inspect_specs:
        insp = a.ok("inspect_function", name=fn)
        body = insp["result"]["body"]
        found = re.findall(
            rf"call name={re.escape(token)} rev=([0-9a-f]{{64}})", body)
        callers.extend(found)
    # de-dup while preserving order
    seen = set()
    return [c for c in callers if not (c in seen or seen.add(c))]


def discover_blocks(a, inspect_blocks):
    blocks = []
    for spec in inspect_blocks or []:
        insp = a.ok("inspect_function", name=spec["fn"])
        body = insp["result"]["body"]
        m = re.search(r"block rev=([0-9a-f]{64})", body)
        if not m:
            fail(f"no block found in {spec['fn']}")
        blocks.append(m.group(1))
    return blocks


def expand(blob, slots):
    out = blob
    for key, val in slots.items():
        out = out.replace("{{" + key + "}}", val)
    return out


def apply_ops(alva, project, manifest, ops):
    a = Agent(alva, project)
    a.ok("begin_transaction", project=project)
    callers = discover_callers(a, manifest.get("inspect", []))
    slots = {}
    for i, b in enumerate(discover_blocks(a, manifest.get("inspect_blocks", []))):
        slots[f"block{i}"] = b
    for op in ops:
        tool = op["tool"]
        args = dict(op.get("args", {}))
        # expand {{caller}} across the requested caller subset
        if "{{caller}}" in json.dumps(args):
            subset = callers
            caller_mode = op.get("callers", "all")
            if caller_mode == "first":
                subset = callers[:1]
            elif caller_mode == "none":
                subset = []
            for c in subset:
                concrete = json.loads(expand(json.dumps(args), dict(slots, caller=c)))
                r = a.ok(tool, **concrete)
                if op.get("as"):
                    slots[op["as"]] = r["result"].get("revision")
        else:
            concrete = json.loads(expand(json.dumps(args), slots))
            r = a.ok(tool, **concrete)
            if op.get("as"):
                slots[op["as"]] = r["result"].get("revision")
    check = a.call("check_transaction")
    commit = a.call("commit_transaction")
    a.close()
    if not (check.get("ok") and commit.get("ok")):
        return False, check.get("message", "")[:200]
    return True, ""


def run_verifier(alva, project, checkspec):
    project_dir = os.path.dirname(project)
    spec_path = os.path.join(project_dir, "_checkspec.json")
    with open(spec_path, "w", encoding="utf-8") as fh:
        json.dump(checkspec, fh)
    p = subprocess.run(
        [sys.executable, VERIFIER, project_dir, spec_path],
        env=dict(os.environ, ALVA=alva), capture_output=True, text=True,
    )
    return p.returncode == 0, (p.stdout + p.stderr)[-400:]


def qualify_one(alva, cand_dir, candidate):
    cid = candidate["id"]
    fixture_dir = os.path.join(cand_dir, candidate["fixture"])
    # 1. baseline project check on pristine fixture.
    base = fresh_copy(fixture_dir)
    p = subprocess.run(
        [alva, "project", "check", base],
        capture_output=True, text=True,
    )
    if p.returncode != 0:
        fail(f"{cid}: baseline project check failed:\n{p.stdout[-500:]}")
    # 2. reference LOW canonical sequence -> commit -> verifier PASS.
    ref = fresh_copy(fixture_dir)
    ok, msg = apply_ops(alva, ref, candidate["low_sequence"],
                        candidate["low_sequence"]["ops"])
    if not ok:
        fail(f"{cid}: reference LOW sequence did not commit: {msg}")
    passed, out = run_verifier(alva, ref, candidate["verifier"])
    if not passed:
        fail(f"{cid}: reference solution rejected by verifier:\n{out}")
    # 3. wrong variants must be rejected.
    for wv in candidate.get("wrong_variants", []):
        wrong = fresh_copy(fixture_dir)
        wok, wmsg = apply_ops(alva, wrong, candidate["low_sequence"], wv["ops"])
        if not wok:
            fail(f"{cid}/{wv['id']}: variant did not commit "
                 f"(expected commit then verifier rejection): {wmsg}")
        wpassed, wout = run_verifier(alva, wrong, candidate["verifier"])
        if wpassed:
            fail(f"{cid}/{wv['id']} ({wv['reason']}): verifier ACCEPTED a "
                 f"wrong solution")
    log(f"{cid} [{candidate['group']}]: QUALIFIED "
        f"({len(candidate.get('wrong_variants', []))} wrong variants "
        f"rejected)")
    return 0


def main():
    if len(sys.argv) < 2:
        print("USAGE: qualify_candidate.py <candidate-dir>...",
              file=sys.stderr)
        return 2
    alva = os.environ.get("ALVA")
    if not alva:
        print("set ALVA to the alva executable", file=sys.stderr)
        return 2
    rc = 0
    for cand_dir in sys.argv[1:]:
        manifest_path = os.path.join(cand_dir, "candidate.json")
        with open(manifest_path, encoding="utf-8") as fh:
            candidate = json.load(fh)
        rc |= qualify_one(alva, cand_dir, candidate)
    log("ALL CANDIDATES QUALIFIED")
    return rc


if __name__ == "__main__":
    sys.exit(main())
