#!/usr/bin/env python3
"""Regression tests for semantic checking on the AIR/AEP path.

Scenario (found during the t05 A/C pilot):
  1. project check/build used to skip the full checker when an authoritative
     AIR store was present, so a type-broken program passed check;
  2. `check_transaction` used to be structural-only, so the broken program
     committed and only `build --test` caught E_CALL_003.

Both are now fixed: the AIR path runs the full checker, and
check_transaction/commit reject semantic errors before writing.

Usage: ALVA=<alva-exe> python tests/air/air_check_soundness_test.py
"""

import json
import os
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


BASE_SRC = """(module
  (name "store.commit")
  (version "0.1.0")
  (export put_object)
  (fn step
    (params (param name (prim string)))
    (returns (prim string))
    (pure)
    (body (ref name)))
  (fn put_object
    (params (param key (prim string)))
    (returns (prim string))
    (pure)
    (body
      (block
        (call step (string "write_blob"))
        (call concat (ref key) (string ":committed"))))))
"""

TOML = "[project]\nname = \"store\"\n\n[modules]\n\"store.commit\" = \"demo.alva\"\n"


def main():
    alva = os.environ.get("ALVA")
    if not alva:
        fail("set ALVA to the alva executable")
    work = tempfile.mkdtemp(prefix="alva-air-check-")
    proj = os.path.join(work, "project")
    os.makedirs(proj)
    with open(os.path.join(proj, "demo.alva"), "w", encoding="utf-8") as fh:
        fh.write(BASE_SRC)
    with open(os.path.join(proj, "alva.toml"), "w", encoding="utf-8") as fh:
        fh.write(TOML)

    # 1. build an authoritative store from the valid text project
    r = run([alva, "air", "export", os.path.join(proj, "alva.toml"),
             "--out-dir", os.path.join(work, "air"), "--authoritative"])
    if r.returncode != 0:
        fail("air export failed: " + r.stderr[-500:])
    os.remove(os.path.join(proj, "demo.alva"))

    # 2. attempt to commit a structurally valid but type-broken program via AEP
    p = subprocess.Popen([alva, "agent"], stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, text=True)

    def tool(obj):
        p.stdin.write(json.dumps(obj) + "\n")
        p.stdin.flush()
        return json.loads(p.stdout.readline())

    r = tool({"tool": "begin_transaction", "project": os.path.join(proj, "alva.toml")})
    if not r.get("ok"):
        fail("begin_transaction failed: " + json.dumps(r))
    r = tool({"tool": "create_literal", "type": "string", "value": "bad"})
    lit = r["result"]["revision"]
    r = tool({"tool": "create_call", "name": "step", "args": []})  # 0 args: type-broken
    call_rev = r["result"]["revision"]
    tool({"tool": "append_step", "function": "store.commit.put_object", "step": call_rev})
    r = tool({"tool": "check_transaction"})
    if r.get("ok"):
        fail("check_transaction must reject the type-broken program (E_CALL_003)")
    if "E_CALL_003" not in json.dumps(r):
        fail("expected E_CALL_003 from check_transaction, got: " + json.dumps(r))
    log("PASS: check_transaction rejects type-broken program with E_CALL_003")
    r = tool({"tool": "commit_transaction"})
    if r.get("ok"):
        fail("commit_transaction must be rejected while the program is type-broken")
    log("PASS: commit_transaction rejected while type-broken")
    tool({"tool": "abort_transaction"})
    p.stdin.close()
    p.wait()

    # 3. nothing was committed: the store still holds the original program
    r = run([alva, "project", "check", os.path.join(proj, "alva.toml")])
    if r.returncode != 0:
        fail("project check failed after aborted broken commit: " +
             (r.stdout + r.stderr)[-400:])
    log("PASS: aborted broken commit left the authoritative store intact")

    # 4. a valid AEP commit must still pass project check (no regression)
    shutil.rmtree(proj)
    os.makedirs(proj)
    with open(os.path.join(proj, "demo.alva"), "w", encoding="utf-8") as fh:
        fh.write(BASE_SRC)
    with open(os.path.join(proj, "alva.toml"), "w", encoding="utf-8") as fh:
        fh.write(TOML)
    r = run([alva, "air", "export", os.path.join(proj, "alva.toml"),
             "--out-dir", os.path.join(work, "air2"), "--authoritative"])
    if r.returncode != 0:
        fail("air export (valid) failed")
    os.remove(os.path.join(proj, "demo.alva"))
    r = run([alva, "project", "check", os.path.join(proj, "alva.toml")])
    if r.returncode != 0:
        fail("project check failed on valid AIR program: " + (r.stdout + r.stderr)[-400:])
    log("PASS: project check still accepts valid AIR program")
    log(f"work dir: {work}")


if __name__ == "__main__":
    main()
