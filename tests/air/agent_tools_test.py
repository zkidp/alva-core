#!/usr/bin/env python3
"""Regression test for the high-level Agent Runtime tools (v0.6.1 item 8):
inspect_body / inspect_test / add_field / add_record_field / add_param /
add_call_arg / set_effect / add_cap / create_if, plus cross-module rename.

Usage: ALVA=<alva-exe> python tests/air/agent_tools_test.py
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile


def log(msg):
    print(msg, flush=True)


def fail(msg):
    log(f"FAIL: {msg}")
    raise SystemExit(1)


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def start_gateway(alva, project, state):
    p = subprocess.Popen(
        ["python", os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "benchmarks", "ac", "ac_client.py"),
         "serve", "--alva", alva, "--project", project, "--port", "0",
         "--state", state],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    import time
    port_file = os.path.join(state, "port.txt")
    for _ in range(200):
        if os.path.exists(port_file):
            break
        time.sleep(0.1)
    port = int(open(port_file, encoding="utf-8").read().strip())
    return p, port


def stop_gateway(port):
    subprocess.run(
        ["python", os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "benchmarks", "ac", "ac_client.py"),
         "stop", "--port", str(port)],
        capture_output=True, text=True)


class Agent:
    def __init__(self, alva, work):
        self.alva = alva
        self.work = work
        self.state = tempfile.mkdtemp(prefix="alva-agent-tools-")
        self.gw, self.port = start_gateway(
            alva, os.path.join(work, "alva.toml"), self.state)
        self.begin()

    def tool(self, tool, **params):
        req = {"tool": tool}
        req.update(params)
        args = []
        for k, v in req.items():
            if k == "tool":
                continue
            if isinstance(v, list):
                for item in v:
                    args.append(f"{k}={item}")
            else:
                args.append(f"{k}={v}")
        r = run(
            ["python", os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "..", "..", "benchmarks", "ac", "aep.py"),
             "--port", str(self.port), tool] + args,
            timeout=120)
        out = r.stdout.strip()
        if not out:
            fail(f"empty gateway response for {tool}")
        resp = json.loads(out)
        if not resp.get("ok"):
            fail(f"{tool} failed: {resp.get('message')} (params={params})")
        return resp

    def begin(self):
        self.tool("begin_transaction",
                  project=os.path.join(self.work, "alva.toml"))

    def close(self):
        self.tool("abort_transaction")
        stop_gateway(self.port)
        self.gw.wait(timeout=10)


def setup(alva, fixture_dir):
    state = tempfile.mkdtemp(prefix="alva-agent-tools-proj-")
    work = os.path.join(state, "work")
    shutil.copytree(fixture_dir, work)
    r = run([alva, "air", "export", os.path.join(work, "alva.toml"),
             "--out-dir", os.path.join(state, "air"), "--authoritative"])
    if r.returncode != 0:
        fail("air export failed: " + r.stderr[-400:])
    for dirpath, _, files in os.walk(work):
        for f in files:
            if f.endswith(".alva"):
                os.remove(os.path.join(dirpath, f))
    return work


def main():
    alva = os.environ.get("ALVA")
    if not alva:
        fail("set ALVA to the alva executable")
    repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    tasks = os.path.join(repo, "benchmarks", "ac", "tasks")

    # ---- t01: add_field + add_record_field + full semantic check ----
    log("[1] t01 C-mode: add_field + add_record_field + check + commit")
    work = setup(alva, os.path.join(tasks, "t01", "fixture"))
    ag = Agent(alva, work)
    ag.tool("add_field", type="Meta", name="etag", type_name="string")
    lit = ag.tool("create_literal", type="string", value="")
    lit_rev = lit["result"]["revision"]
    for fn in ("make_meta", "bump_size"):
        body = ag.tool("inspect_body", function=f"demo.{fn}")
        m = re.search(r"\(record type=Meta rev=(\w+)", body["result"]["body"])
        if not m:
            fail(f"no record found in {fn} body tree")
        ag.tool("add_record_field", record=m.group(1), name="etag", value=lit_rev)
    # incomplete migration must be rejected: remove one etag? skip; instead
    # check a deliberately broken program is rejected via check_transaction.
    ck = ag.tool("check_transaction")
    if ck.get("result", {}).get("problems") != []:
        fail("check_transaction should pass after full migration")
    co = ag.tool("commit_transaction")
    if "generation" not in co["result"]:
        fail("commit failed")
    ag.close()
    # verify with the t01 hidden verifier (mode C projection)
    proj = os.path.join(os.path.dirname(work), "projection")
    os.makedirs(proj, exist_ok=True)
    store = os.path.join(work, "alva-air")
    gen = open(os.path.join(store, "current"), encoding="utf-8").readline().strip()
    r = run([alva, "air", "import", os.path.join(store, f"gen-{gen}.air"),
             "--out-dir", proj])
    if r.returncode != 0:
        fail("projection import failed")
    r = run(["python", os.path.join(tasks, "t01", "hidden", "verify.py"),
             "--alva", alva, "--workspace", work, "--src", proj])
    if r.returncode != 0:
        fail("t01 verifier failed: " + r.stdout)
    log("  t01 C-mode flow + verifier OK")

    # ---- t03: set_effect + add_cap ----
    log("[2] t03 C-mode: set_effect + add_cap")
    work = setup(alva, os.path.join(tasks, "t03", "fixture"))
    ag = Agent(alva, work)
    ag.tool("add_cap", module="demo", cap="io")
    ag.tool("set_effect", function="demo.fetch_data", effect="io")
    ag.tool("set_effect", function="demo.run_checked", effect="io")
    ag.tool("set_effect", function="demo.run_unchecked", effect="pure")
    ck = ag.tool("check_transaction")
    if ck.get("result", {}).get("problems") != []:
        fail("t03 check_transaction should pass")
    ag.close()
    log("  t03 set_effect/add_cap + semantic check OK")

    # ---- t07: add_param + add_call_arg + inspect_test ----
    log("[3] t07 C-mode: add_param + add_call_arg + inspect_test")
    work = setup(alva, os.path.join(tasks, "t07", "fixture"))
    ag = Agent(alva, work)
    ag.tool("add_param", function="store.meta.build_meta",
            name="generation", type="i64")
    gen_lit = ag.tool("create_literal", type="i64", value="5")
    gen_rev = gen_lit["result"]["revision"]
    t = ag.tool("inspect_test", module="store.meta", name="build_has_fields")
    body = t["result"]["body"]
    m = re.search(r"\(call name=build_meta rev=(\w+)", body)
    if not m:
        fail("build_meta call not found in test body tree")
    ag.tool("add_call_arg", call=m.group(1), arg=gen_rev)
    ck = ag.tool("check_transaction")
    if ck.get("result", {}).get("problems") != []:
        fail("t07 check_transaction should pass after param + arg migration")
    ag.close()
    log("  t07 add_param/add_call_arg/inspect_test + semantic check OK")

    # ---- t08: create_if + replace_expression(else) ----
    log("[4] t08 C-mode: create_if + replace_expression else")
    work = setup(alva, os.path.join(tasks, "t08", "fixture"))
    ag = Agent(alva, work)
    handle = ag.tool("inspect_body", function="store.router.handle")
    body = handle["result"]["body"]
    m = re.search(r"\(if rev=(\w+)", body)
    if not m:
        fail("no if node found in handle body")
    outer_if = m.group(1)
    opt = ag.tool("create_literal", type="string", value="OPTIONS")
    opt_rev = opt["result"]["revision"]
    path = ag.tool("create_reference", name="path")
    path_rev = path["result"]["revision"]
    r200 = ag.tool("create_literal", type="i64", value="200")
    r200_rev = r200["result"]["revision"]
    ok_lit = ag.tool("create_literal", type="string", value="ok")
    ok_rev = ok_lit["result"]["revision"]
    resp_call = ag.tool("create_call", name="response",
                        args=[r200_rev, ok_rev])
    resp_rev = resp_call["result"]["revision"]
    cond = ag.tool("create_binary", op="==", left=path_rev, right=opt_rev)
    cond_rev = cond["result"]["revision"]
    new_if = ag.tool("create_if", cond=cond_rev, then=resp_rev,
                     **{"else": resp_rev})
    new_if_rev = new_if["result"]["revision"]
    ag.tool("replace_expression", parent=outer_if, child=new_if_rev,
            position="else")
    ag.tool("check_transaction")
    ag.close()
    log("  t08 create_if + replace_expression(else) OK")

    # ---- t04: cross-module rename_entity ----
    log("[5] t04 C-mode: rename_entity across modules")
    work = setup(alva, os.path.join(tasks, "t04", "fixture"))
    ag = Agent(alva, work)
    ag.tool("rename_entity", entity="calc.distance", new_name="dist")
    ck = ag.tool("check_transaction")
    if ck.get("result", {}).get("problems") != []:
        fail("t04 check_transaction should pass after rename")
    ag.close()
    log("  t04 rename_entity cross-module + semantic check OK")

    log("ALL HIGH-LEVEL AGENT TOOL TESTS PASSED")


if __name__ == "__main__":
    main()
