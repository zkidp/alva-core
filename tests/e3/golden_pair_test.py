#!/usr/bin/env python3
"""E3 golden-pair tests (zero-model): HIGH migrate_signature vs the canonical
LOW primitive sequence, qualified across caller multiplicity, nesting,
module boundaries, duplicate callee names, and invalid inputs.

Cases (GOLDEN-PAIR-SPEC.md):
  GP01 one caller
  GP02 many callers (multiple functions)
  GP03 zero callers
  GP04 nested call
  GP05 cross-module caller (qualified name)
  GP06 duplicate callee names in two modules (target module scoping)
  GP07 invalid entity
  GP08 invalid type/value
  gate-OFF inertness

Usage: ALVA=<alva-exe> python tests/e3/golden_pair_test.py
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, "fixtures")
ENV = dict(os.environ)
ENV.setdefault("ALVA_AEP_ENABLE_EXPERIMENTAL_A1", "1")

CASES = [
    dict(name="GP01 one caller", fixture="gp01_one_caller",
         target="gp.main.compute",
         inspect=[("gp.main.run", "compute")]),
    dict(name="GP02 many callers", fixture="gp02_many_callers",
         target="gp.main.compute",
         inspect=[("gp.main.run", "compute"), ("gp.main.run2", "compute")]),
    dict(name="GP03 zero callers", fixture="gp03_zero_callers",
         target="gp.main.compute", inspect=[]),
    dict(name="GP04 nested call", fixture="gp04_nested_call",
         target="gp.main.compute",
         inspect=[("gp.main.run", "compute")]),
    dict(name="GP05 cross-module caller", fixture="gp05_cross_module",
         target="gp.a.compute",
         inspect=[("gp.b.caller_b", "gp.a.compute")]),
    dict(name="GP06 duplicate callee names", fixture="gp06_dup_names",
         target="gp.a.compute",
         inspect=[("gp.a.caller_a", "compute")],
         untouched_module="module:gp.b"),
]


def fail(msg):
    print(f"FAIL: {msg}", flush=True)
    raise SystemExit(1)


def log(msg):
    print(msg, flush=True)


class Agent:
    def __init__(self, alva, project, gate_on):
        env = dict(ENV)
        if gate_on:
            env["ALVA_AEP_ENABLE_E3_HIGH"] = "1"
        else:
            env.pop("ALVA_AEP_ENABLE_E3_HIGH", None)
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


def fresh_project(fixture):
    work = tempfile.mkdtemp(prefix="gp-")
    proj_dir = os.path.join(work, "proj")
    shutil.copytree(os.path.join(FIXTURES, fixture), proj_dir)
    return os.path.join(proj_dir, "alva.toml")


def state_heads(alva, project):
    """Open the project (source or committed store) in a fresh cmd_edit
    process and return (semantic_hash, sorted module heads)."""
    p = subprocess.Popen(
        [alva, "edit"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        text=True, encoding="utf-8",
    )
    p.stdin.write(json.dumps({"op": "begin", "project": project}) + "\n")
    p.stdin.flush()
    line = p.stdout.readline()
    p.stdin.close()
    p.wait()
    r = json.loads(line)
    if not r.get("ok"):
        fail(f"state begin failed: {r}")
    res = r["result"]
    return res["base_hash"], res["modules"]


def run_arm(alva, case, mode):
    project = fresh_project(case["fixture"])
    a = Agent(alva, project, gate_on=(mode == "high"))
    a.ok("begin_transaction", project=project)
    if mode == "high":
        a.ok("migrate_signature", function=case["target"],
             param="factor", type="i64", value="2")
    else:
        callers = set()
        for fn, token in case["inspect"]:
            insp = a.ok("inspect_function", name=fn)
            body = insp["result"]["body"]
            pat = rf"call name={re.escape(token)} rev=([0-9a-f]{{64}})"
            callers.update(re.findall(pat, body))
        a.ok("add_param", function=case["target"], name="factor", type="i64")
        lit = a.ok("create_literal", type="i64", value="2")
        arg_rev = lit["result"]["revision"]
        for c in sorted(callers):
            a.ok("add_call_arg", call=c, arg=arg_rev)
    check = a.call("check_transaction")
    commit = a.call("commit_transaction")
    a.close()
    return project, check, commit


def run_case(alva, case):
    low_proj, low_check, low_commit = run_arm(alva, case, "low")
    high_proj, high_check, high_commit = run_arm(alva, case, "high")
    # Layer 2: validation equivalence.
    if low_check["ok"] != high_check["ok"]:
        fail(f"{case['name']}: check differs: LOW {low_check.get('message')} "
             f"vs HIGH {high_check.get('message')}")
    if low_commit["ok"] != high_commit["ok"]:
        fail(f"{case['name']}: commit differs: LOW {low_commit.get('message')} "
             f"vs HIGH {high_commit.get('message')}")
    if not (low_check["ok"] and low_commit["ok"]):
        fail(f"{case['name']}: expected both arms to pass check and commit")
    # Layer 1: final authoritative state equality.
    low_state = state_heads(alva, low_proj)
    high_state = state_heads(alva, high_proj)
    if low_state != high_state:
        fail(f"{case['name']}: final state differs:\n  LOW  {low_state}\n"
             f"  HIGH {high_state}")
    # GP06: duplicate-name target must NOT touch the other module.
    untouched = case.get("untouched_module")
    if untouched:
        baseline = state_heads(alva, fresh_project(case["fixture"]))
        if high_state[1][untouched] != baseline[1][untouched]:
            fail(f"{case['name']}: untouched module {untouched} was modified: "
                 f"{baseline[1][untouched]} -> {high_state[1][untouched]}")
    log(f"{case['name']}: PASS (final hash {low_state[0][:12]}..., "
        f"heads match)")


def negative_cases(alva):
    # GP07: unknown entity rejected by both arms.
    p1 = fresh_project("gp01_one_caller")
    a = Agent(alva, p1, gate_on=True)
    a.ok("begin_transaction", project=p1)
    high_unknown = a.call("migrate_signature", function="gp.main.nope",
                          param="factor", type="i64", value="2")
    a.close()
    p2 = fresh_project("gp01_one_caller")
    b = Agent(alva, p2, gate_on=False)
    b.ok("begin_transaction", project=p2)
    low_unknown = b.call("add_param", function="gp.main.nope",
                         name="factor", type="i64")
    b.close()
    if high_unknown["ok"] or low_unknown["ok"]:
        fail(f"GP07 unknown entity must be rejected: HIGH {high_unknown}, "
             f"LOW {low_unknown}")
    # GP08: invalid type/value rejected by both arms.
    p3 = fresh_project("gp01_one_caller")
    c = Agent(alva, p3, gate_on=True)
    c.ok("begin_transaction", project=p3)
    high_bad = c.call("migrate_signature", function="gp.main.compute",
                      param="factor", type="i64", value="not-an-int")
    c.close()
    p4 = fresh_project("gp01_one_caller")
    d = Agent(alva, p4, gate_on=False)
    d.ok("begin_transaction", project=p4)
    low_bad = d.call("create_literal", type="i64", value="not-an-int")
    d.close()
    if high_bad["ok"] or low_bad["ok"]:
        fail(f"GP08 invalid literal must be rejected: HIGH {high_bad}, "
             f"LOW {low_bad}")
    log("GP07 invalid entity: PASS (rejected in both arms)")
    log("GP08 invalid type/value: PASS (rejected in both arms)")


def gate_off_inert(alva):
    project = fresh_project("gp01_one_caller")
    a = Agent(alva, project, gate_on=False)
    a.ok("begin_transaction", project=project)
    r = a.call("migrate_signature", function="gp.main.compute",
               param="factor", type="i64", value="2")
    a.close()
    if r.get("ok") or "E_AEP_UNKNOWN_TOOL" not in r.get("error_code", ""):
        fail(f"gate OFF must make migrate_signature inert, got {r}")
    log("GATE-OFF INERTNESS: PASS")


def main():
    alva = os.environ.get("ALVA")
    if not alva:
        fail("set ALVA to the alva executable")
    for case in CASES:
        run_case(alva, case)
    negative_cases(alva)
    gate_off_inert(alva)
    log("GOLDEN-PAIR SUITE: PASS")


if __name__ == "__main__":
    main()
