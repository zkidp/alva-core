#!/usr/bin/env python3
"""E3 golden-pair tests (zero-model): HIGH migrate_signature vs the canonical
LOW primitive sequence on a frozen fixture.

Layers (GOLDEN-PAIR-SPEC.md):
  1. success: same final authoritative state (semantic hash + entity heads)
  2. validation: same check result / commit admissibility
  3. failure: same rejection of invalid inputs; gate-OFF inertness

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
FIXTURE = os.path.join(HERE, "fixtures", "gp_basic")
ENV = dict(os.environ)
ENV.setdefault("ALVA_AEP_ENABLE_EXPERIMENTAL_A1", "1")


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


def fresh_project():
    work = tempfile.mkdtemp(prefix="gp-")
    proj_dir = os.path.join(work, "proj")
    shutil.copytree(FIXTURE, proj_dir)
    return os.path.join(proj_dir, "alva.toml")


def final_state(alva, project):
    """Open the committed authoritative store in a fresh cmd_edit process and
    return (semantic_hash, module heads) of the final state."""
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
        fail(f"final-state begin failed: {r}")
    res = r["result"]
    return res["base_hash"], sorted(res["modules"])


def run_arm(alva, mode):
    project = fresh_project()
    a = Agent(alva, project, gate_on=(mode == "high"))
    a.ok("begin_transaction", project=project)
    if mode == "high":
        a.ok("migrate_signature", function="gp.main.compute",
             param="factor", type="i64", value="2")
    else:
        insp = a.ok("inspect_function", name="gp.main.run")
        body = insp["result"]["body"]
        callers = re.findall(r"call name=compute rev=([0-9a-f]{64})", body)
        if len(callers) != 2:
            fail(f"expected 2 compute call sites, found {len(callers)}: {callers}")
        a.ok("add_param", function="gp.main.compute", name="factor", type="i64")
        lit = a.ok("create_literal", type="i64", value="2")
        arg_rev = lit["result"]["revision"]
        for c in sorted(set(callers)):
            a.ok("add_call_arg", call=c, arg=arg_rev)
    check = a.call("check_transaction")
    commit = a.call("commit_transaction")
    a.close()
    return project, check, commit


def layer1_success(alva):
    low_proj, low_check, low_commit = run_arm(alva, "low")
    high_proj, high_check, high_commit = run_arm(alva, "high")
    # Layer 2: validation equivalence (check + commit admissibility).
    if low_check["ok"] != high_check["ok"]:
        fail(f"check differs: LOW {low_check.get('message')} vs "
             f"HIGH {high_check.get('message')}")
    if low_commit["ok"] != high_commit["ok"]:
        fail(f"commit differs: LOW {low_commit.get('message')} vs "
             f"HIGH {high_commit.get('message')}")
    if not (low_check["ok"] and low_commit["ok"]):
        fail("success fixture expected both arms to pass check and commit")
    # Layer 1: final authoritative state (semantic hash + entity heads).
    low_state = final_state(alva, low_proj)
    high_state = final_state(alva, high_proj)
    if low_state != high_state:
        fail(f"final state differs:\n  LOW  {low_state}\n  HIGH {high_state}")
    log(f"LAYER 1+2 (success + validation): PASS "
        f"(final semantic hash {low_state[0][:12]}..., heads match)")


def layer3_failure(alva):
    # unknown function: HIGH and LOW must both reject
    p1 = fresh_project()
    a = Agent(alva, p1, gate_on=True)
    a.ok("begin_transaction", project=p1)
    high_unknown = a.call("migrate_signature", function="gp.main.nope",
                          param="factor", type="i64", value="2")
    a.close()
    p2 = fresh_project()
    b = Agent(alva, p2, gate_on=False)
    b.ok("begin_transaction", project=p2)
    low_unknown = b.call("add_param", function="gp.main.nope",
                         name="factor", type="i64")
    b.close()
    if high_unknown["ok"] or low_unknown["ok"]:
        fail(f"unknown function must be rejected: HIGH {high_unknown}, "
             f"LOW {low_unknown}")
    # bad literal value: HIGH and LOW must both reject
    p3 = fresh_project()
    c = Agent(alva, p3, gate_on=True)
    c.ok("begin_transaction", project=p3)
    high_bad = c.call("migrate_signature", function="gp.main.compute",
                      param="factor", type="i64", value="not-an-int")
    c.close()
    p4 = fresh_project()
    d = Agent(alva, p4, gate_on=False)
    d.ok("begin_transaction", project=p4)
    low_bad = d.call("create_literal", type="i64", value="not-an-int")
    d.close()
    if high_bad["ok"] or low_bad["ok"]:
        fail(f"bad literal must be rejected: HIGH {high_bad}, LOW {low_bad}")
    log("LAYER 3 (failure equivalence): PASS (unknown entity and bad literal "
        "rejected in both arms)")


def gate_off_inert(alva):
    project = fresh_project()
    a = Agent(alva, project, gate_on=False)
    a.ok("begin_transaction", project=project)
    r = a.call("migrate_signature", function="gp.main.compute",
               param="factor", type="i64", value="2")
    a.close()
    if r.get("ok") or "E_AEP_UNKNOWN_TOOL" not in r.get("error_code", ""):
        fail(f"gate OFF must make migrate_signature inert, got {r}")
    log("GATE-OFF INERTNESS: PASS (migrate_signature hidden and inert)")


def main():
    alva = os.environ.get("ALVA")
    if not alva:
        fail("set ALVA to the alva executable")
    layer1_success(alva)
    layer3_failure(alva)
    gate_off_inert(alva)
    log("GOLDEN-PAIR SUITE: PASS")


if __name__ == "__main__":
    main()
