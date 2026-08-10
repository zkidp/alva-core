#!/usr/bin/env python3
"""AIR + AEP tests for the source-less typed program construction layer (v0.5.1).

Covers:
  1. air export -> verify -> import -> re-export: semantic hashes identical;
  2. re-imported canonical .alva project passes the real checker;
  3. AEP: begin -> create nodes -> append function -> check -> commit writes the
     authoritative store (generation + atomic CURRENT), project check consumes
     AIR, and the canonical projection contains the new function;
  4. AIR invariant: after every AEP operation the graph passes full verify;
  5. corruption: tampered generation files are rejected on load;
  6. crash safety: a stray/incomplete generation never moves CURRENT; the
     authoritative store keeps loading the last committed generation;
  7. concurrency: a commit based on a stale base revision is rejected;
  8. views (module/function/dependencies) and typed holes (inspect/candidates)
     with accurate lexical scope.

Usage: ALVA=<alva-exe> python tests/air/air_test.py
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
    p = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if p.returncode != 0:
        fail(f"command failed: {' '.join(cmd)}\n{p.stdout[-800:]}\n{p.stderr[-800:]}")
    return p.stdout


class Edit:
    def __init__(self, alva, project):
        self.p = subprocess.Popen(
            [alva, "edit"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True
        )
        self.project = project

    def send(self, obj):
        self.p.stdin.write(json.dumps(obj) + "\n")
        self.p.stdin.flush()
        line = self.p.stdout.readline()
        if not line.strip():
            raise RuntimeError(f"edit process closed while sending {obj}")
        return json.loads(line)

    def ok(self, obj):
        r = self.send(obj)
        if not r.get("ok"):
            fail(f"op {obj.get('op')} failed: {r}")
        return r

    def close(self):
        self.p.stdin.close()
        self.p.wait()


def main():
    alva = os.environ.get("ALVA")
    if not alva:
        fail("set ALVA to the alva executable")
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    project = os.path.join(root, "examples", "store_split", "alva.toml")
    work = tempfile.mkdtemp(prefix="alva-air-test-")

    # ---- 1. round-trip hash stability ----
    log("[1] AIR export/import round-trip hash stability")
    base_dir = os.path.join(work, "base")
    out = run([alva, "air", "export", project, "--out-dir", base_dir])
    original = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0].startswith("store."):
            original[parts[0]] = parts[1]
    if len(original) < 10:
        fail(f"expected 10 modules, got {len(original)}")
    run([alva, "air", "verify", os.path.join(base_dir, "store.air")])
    rt_dir = os.path.join(work, "rt")
    run([alva, "air", "import", os.path.join(base_dir, "store.air"), "--out-dir", rt_dir])
    toml = "[project]\nname = \"store\"\n\n[modules]\n"
    for f in sorted(os.listdir(rt_dir)):
        if f.endswith(".alva"):
            toml += f'"{os.path.splitext(f)[0]}" = "{f}"\n'
    with open(os.path.join(rt_dir, "alva.toml"), "w", encoding="utf-8") as fh:
        fh.write(toml)
    run([alva, "project", "check", os.path.join(rt_dir, "alva.toml")])
    rt2 = os.path.join(work, "rt2")
    out2 = run([alva, "air", "export", os.path.join(rt_dir, "alva.toml"), "--out-dir", rt2])
    roundtrip = {}
    for line in out2.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0].startswith("store."):
            roundtrip[parts[0]] = parts[1]
    for name in original:
        if original[name] != roundtrip.get(name):
            fail(f"module {name} semantic hash changed after round-trip")
    log("  ok")

    # ---- 1b. contains overload round-trip (map vs vec semantic identity) ----
    # RFC-0003: 裸 (contains v x) 是 vec element contains；(call contains m k)
    # 是 map key contains。projection 必须让两者在 export -> import ->
    # re-export 后保持同一语义（hash 不变，且 re-import 后 checker 通过）。
    log("[1b] contains overload round-trip (map/vec semantic identity)")
    qproj = os.path.join(root, "tests", "air", "contains_roundtrip", "alva.toml")
    qbase = os.path.join(work, "qbase")
    qout = run([alva, "air", "export", qproj, "--out-dir", qbase])
    qoriginal = {}
    for line in qout.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0].startswith("ct_rt."):
            qoriginal[parts[0]] = parts[1]
    if len(qoriginal) != 1:
        fail(f"expected 1 module, got {len(qoriginal)}")
    run([alva, "air", "verify", os.path.join(qbase, "ct_rt.air")])
    qrt = os.path.join(work, "qrt")
    run([alva, "air", "import", os.path.join(qbase, "ct_rt.air"), "--out-dir", qrt])
    with open(os.path.join(qrt, "alva.toml"), "w", encoding="utf-8") as fh:
        fh.write('[project]\nname = "ct_rt"\n\n[modules]\n"ct_rt.x" = "ct_rt.x.alva"\n')
    run([alva, "project", "check", os.path.join(qrt, "alva.toml")])
    qrt2 = os.path.join(work, "qrt2")
    qout2 = run([alva, "air", "export", os.path.join(qrt, "alva.toml"), "--out-dir", qrt2])
    qroundtrip = {}
    for line in qout2.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0].startswith("ct_rt."):
            qroundtrip[parts[0]] = parts[1]
    for name in qoriginal:
        if qoriginal[name] != qroundtrip.get(name):
            fail(f"module {name} semantic hash changed after contains round-trip")
    log("  ok (map contains stays (call contains ...), vec contains stays (contains ...))")

    # ---- 2+3+4. AEP edit, invariant after each op, authoritative commit ----
    log("[2] AEP structured edit + invariant after every op + authoritative commit")
    aep_proj = os.path.join(work, "aep")
    shutil.copytree(os.path.join(root, "examples", "store_split"), aep_proj)
    run([alva, "air", "export", os.path.join(aep_proj, "alva.toml"),
         "--out-dir", os.path.join(work, "aep-base"), "--authoritative"])
    ed = Edit(alva, os.path.join(aep_proj, "alva.toml"))
    r = ed.ok({"op": "begin", "project": os.path.join(aep_proj, "alva.toml")})
    base_hash = r["result"]["base_hash"]
    r = ed.ok({"op": "create_node", "kind": "type_expr",
               "fields": {"shape": "prim", "name": "string"}})
    ret = r["result"]["revision"]
    r = ed.ok({"op": "create_node", "kind": "literal",
               "fields": {"value": "hello from AEP"}})
    lit = r["result"]["revision"]
    r = ed.ok({"op": "create_node", "kind": "block", "slots": {"steps": [lit]}})
    body = r["result"]["revision"]
    r = ed.ok({"op": "create_node", "kind": "function",
               "fields": {"name": "hello_from_aep", "pure": True, "eff": []},
               "slots": {"params": [], "returns": [ret], "body": [body],
                         "pre": [], "post": [], "inv": []}})
    fn = r["result"]["revision"]
    ed.ok({"op": "check"})  # invariant: graph verifies after each create
    r = ed.ok({"op": "append_child", "parent": "module:store.model",
               "slot": "functions", "child": fn})
    if not r["result"]["new_parent_revision"]:
        fail("append_child returned no new parent revision")
    ed.ok({"op": "check"})  # invariant after structural edit
    r = ed.ok({"op": "commit"})
    gen = r["result"]["generation"]
    if gen < 2:
        fail(f"expected generation >= 2, got {gen}")
    ed.close()
    run([alva, "project", "check", os.path.join(aep_proj, "alva.toml")])
    proj_out = os.path.join(work, "proj")
    run([alva, "air", "import", os.path.join(aep_proj, "alva-air", f"gen-{gen}.air"),
         "--out-dir", proj_out])
    model_src = open(os.path.join(proj_out, "store.model.alva"), encoding="utf-8").read()
    if "hello_from_aep" not in model_src:
        fail("committed function not present in canonical projection")
    log("  ok")

    # ---- 5. corruption ----
    log("[3] corrupted generation rejected")
    store = os.path.join(aep_proj, "alva-air")
    gen_path = os.path.join(store, f"gen-{gen}.air")
    data = bytearray(open(gen_path, "rb").read())
    data[len(data) // 2] ^= 0xFF
    bad_path = os.path.join(store, "gen-999.air")
    with open(bad_path, "wb") as fh:
        fh.write(bytes(data))
    cur = os.path.join(store, "current")
    with open(cur, "w", encoding="utf-8") as fh:
        fh.write(f"999\ncorrupt\n")
    p = subprocess.run([alva, "project", "check", os.path.join(aep_proj, "alva.toml")],
                       capture_output=True, text=True)
    if p.returncode == 0:
        fail("corrupted generation was accepted")
    log("  ok")

    # ---- 6. crash safety: stray generation never moves CURRENT ----
    log("[4] stray/incomplete generation does not break the authoritative store")
    crash_proj = os.path.join(work, "crash")
    shutil.copytree(os.path.join(root, "examples", "store_split"), crash_proj)
    run([alva, "air", "export", os.path.join(crash_proj, "alva.toml"),
         "--out-dir", os.path.join(work, "crash-base"), "--authoritative"])
    cstore = os.path.join(crash_proj, "alva-air")
    with open(os.path.join(cstore, "gen-999.air.tmp"), "wb") as fh:
        fh.write(b"partial")
    with open(os.path.join(cstore, "current.tmp"), "w", encoding="utf-8") as fh:
        fh.write("999\npartial\n")
    run([alva, "project", "check", os.path.join(crash_proj, "alva.toml")])
    current = open(os.path.join(cstore, "current"), encoding="utf-8").read()
    if current.splitlines()[0].strip() != "1":
        fail("CURRENT moved to an incomplete generation")
    log("  ok")

    # ---- 7. concurrency: stale base revision rejected ----
    log("[5] concurrent commit with stale base revision rejected")
    conc_proj = os.path.join(work, "conc")
    shutil.copytree(os.path.join(root, "examples", "store_split"), conc_proj)
    run([alva, "air", "export", os.path.join(conc_proj, "alva.toml"),
         "--out-dir", os.path.join(work, "conc-base"), "--authoritative"])
    e1 = Edit(alva, os.path.join(conc_proj, "alva.toml"))
    r1 = e1.ok({"op": "begin", "project": os.path.join(conc_proj, "alva.toml")})
    # session 2 commits a no-op change first (bumps generation)
    e2 = Edit(alva, os.path.join(conc_proj, "alva.toml"))
    e2.ok({"op": "begin", "project": os.path.join(conc_proj, "alva.toml")})
    r = e2.ok({"op": "create_node", "kind": "literal", "fields": {"value": "x"}})
    lit = r["result"]["revision"]
    r = e2.ok({"op": "create_node", "kind": "block", "slots": {"steps": [lit]}})
    body = r["result"]["revision"]
    r = e2.ok({"op": "create_node", "kind": "type_expr",
               "fields": {"shape": "prim", "name": "i64"}})
    ret = r["result"]["revision"]
    r = e2.ok({"op": "create_node", "kind": "function",
               "fields": {"name": "second_edit", "pure": True, "eff": []},
               "slots": {"params": [], "returns": [ret], "body": [body],
                         "pre": [], "post": [], "inv": []}})
    fn = r["result"]["revision"]
    e2.ok({"op": "append_child", "parent": "module:store.model",
           "slot": "functions", "child": fn})
    e2.ok({"op": "commit"})
    e2.close()
    # session 1 now has a stale base revision -> commit must be rejected
    r = e1.send({"op": "commit"})
    if r.get("ok"):
        fail("stale-base commit was accepted")
    if "E_AEP_CONFLICT" not in r.get("message", ""):
        fail(f"expected concurrent-modification rejection, got {r}")
    e1.send({"op": "abort"})
    e1.close()
    log("  ok")

    # ---- 8. views ----
    log("[6] agent views")
    v = run([alva, "view", "module", os.path.join(base_dir, "store.air"),
             "store.storage_commit", "--budget", "2"])
    if "fn put_object" not in v:
        fail("module view missing put_object")
    v = run([alva, "view", "function", os.path.join(base_dir, "store.air"),
             "store.storage_commit.put_object"])
    if "param data_root" not in v:
        fail("function view missing params")
    v = run([alva, "view", "dependencies", os.path.join(base_dir, "store.air"),
             "store.router"])
    if "store.storage_commit" not in v:
        fail("dependencies view missing dep")
    log("  ok")

    # ---- 9. typed holes + lexical scope ----
    log("[7] typed holes with lexical scope")
    hole_proj = os.path.join(work, "hole")
    os.makedirs(hole_proj)
    src = (
        '(module\n  (name "h")\n  (version "0.1.0")\n  (export f)\n'
        '  (fn f (params) (returns (prim string)) (pure)\n'
        '    (body\n'
        '      (let a (string "aa")\n'
        '        (let b (concat (ref a) (string "bb"))\n'
        '          (ref b))))))\n'
    )
    with open(os.path.join(hole_proj, "h.alva"), "w", encoding="utf-8") as fh:
        fh.write(src)
    with open(os.path.join(hole_proj, "alva.toml"), "w", encoding="utf-8") as fh:
        fh.write('[project]\nname = "h"\n\n[modules]\n"h" = "h.alva"\n')
    ed = Edit(alva, os.path.join(hole_proj, "alva.toml"))
    ed.ok({"op": "begin", "project": os.path.join(hole_proj, "alva.toml")})
    r = ed.ok({"op": "create_hole", "expected_type": "string", "allowed_effects": []})
    hole = r["result"]["revision"]
    snap = os.path.join(work, "snapshot.air")
    ed.ok({"op": "snapshot", "path": snap})
    ed.send({"op": "abort"})
    ed.close()
    run([alva, "air", "verify", snap])
    v = run([alva, "hole", "inspect", snap, hole[:16]])
    if "expected_type=string" not in v:
        fail(f"hole inspect wrong: {v}")
    v = run([alva, "hole", "candidates", snap, hole[:16]])
    if "literal" not in v:
        fail(f"hole candidates wrong: {v}")
    log("  ok")

    # ---- 10. dangling child rejected with E_AIR_DANGLING_CHILD ----
    log("[8] dangling child rejected (no panic)")
    dg_proj = os.path.join(work, "dangling")
    os.makedirs(dg_proj)
    with open(os.path.join(dg_proj, "h.alva"), "w", encoding="utf-8") as fh:
        fh.write('(module (name "h") (version "0.1.0") (export f)'
                 ' (fn f (params) (returns (prim i64)) (pure) (body (int 1))))\n')
    with open(os.path.join(dg_proj, "alva.toml"), "w", encoding="utf-8") as fh:
        fh.write('[project]\nname = "h"\n\n[modules]\n"h" = "h.alva"\n')
    ed = Edit(alva, os.path.join(dg_proj, "alva.toml"))
    ed.ok({"op": "begin", "project": os.path.join(dg_proj, "alva.toml")})
    r = ed.send({"op": "create_node", "kind": "block",
                 "slots": {"steps": ["0" * 64]}})
    if r.get("ok") or "E_AIR_DANGLING_CHILD" not in r.get("message", ""):
        fail(f"dangling child not rejected: {r}")
    ed.send({"op": "abort"})
    ed.close()
    log("  ok")

    # ---- 11. cycle rejected before mutation + atomic rollback ----
    log("[9] cycle rejected atomically (session graph unchanged)")
    cyc_proj = os.path.join(work, "cycle")
    shutil.copytree(os.path.join(root, "examples", "store_split"), cyc_proj)
    run([alva, "air", "export", os.path.join(cyc_proj, "alva.toml"),
         "--out-dir", os.path.join(work, "cyc-base"), "--authoritative"])
    ed = Edit(alva, os.path.join(cyc_proj, "alva.toml"))
    r = ed.ok({"op": "begin", "project": os.path.join(cyc_proj, "alva.toml")})
    base_hash = r["result"]["base_hash"]
    snap1 = os.path.join(work, "cycle-before.air")
    ed.ok({"op": "snapshot", "path": snap1})
    # attempt to append the module itself into its own functions slot -> cycle
    r = ed.send({"op": "append_child", "parent": "module:store.model",
                 "slot": "functions", "child": r["result"]["modules"]["module:store.model"]})
    if r.get("ok") or "E_AIR_CYCLE" not in r.get("message", ""):
        fail(f"cycle not rejected: {r}")
    snap2 = os.path.join(work, "cycle-after.air")
    ed.ok({"op": "snapshot", "path": snap2})
    with open(snap1, "rb") as fh:
        b1 = fh.read()
    with open(snap2, "rb") as fh:
        b2 = fh.read()
    if b1 != b2:
        fail("session graph changed after rejected cycle op (no atomic rollback)")
    # a subsequent valid operation still works
    r = ed.ok({"op": "create_node", "kind": "literal", "fields": {"value": "ok"}})
    ed.send({"op": "abort"})
    ed.close()
    log("  ok")

    # ---- 12. two real parallel committers ----
    log("[10] parallel concurrent commits (store lock)")
    par_proj = os.path.join(work, "par")
    shutil.copytree(os.path.join(root, "examples", "store_split"), par_proj)
    run([alva, "air", "export", os.path.join(par_proj, "alva.toml"),
         "--out-dir", os.path.join(work, "par-base"), "--authoritative"])
    import threading
    results = {}

    def committer(name):
        ed = Edit(alva, os.path.join(par_proj, "alva.toml"))
        r = ed.ok({"op": "begin", "project": os.path.join(par_proj, "alva.toml")})
        r = ed.ok({"op": "create_node", "kind": "literal",
                   "fields": {"value": name}})
        lit = r["result"]["revision"]
        r = ed.ok({"op": "create_node", "kind": "block", "slots": {"steps": [lit]}})
        body = r["result"]["revision"]
        r = ed.ok({"op": "create_node", "kind": "type_expr",
                   "fields": {"shape": "prim", "name": "string"}})
        ret = r["result"]["revision"]
        r = ed.ok({"op": "create_node", "kind": "function",
                   "fields": {"name": f"fn_{name}", "pure": True, "eff": []},
                   "slots": {"params": [], "returns": [ret], "body": [body],
                             "pre": [], "post": [], "inv": []}})
        fn = r["result"]["revision"]
        ed.ok({"op": "append_child", "parent": "module:store.model",
               "slot": "functions", "child": fn})
        r = ed.send({"op": "commit"})
        results[name] = r
        try:
            ed.send({"op": "abort"})
        except Exception:
            pass
        ed.close()

    t1 = threading.Thread(target=committer, args=("one",))
    t2 = threading.Thread(target=committer, args=("two",))
    t1.start(); t2.start()
    t1.join(); t2.join()
    wins = [k for k, r in results.items() if r.get("ok")]
    loses = [k for k, r in results.items() if not r.get("ok")]
    if len(wins) != 1:
        fail(f"expected exactly one successful committer, got {wins} ({results})")
    if len(loses) != 1 or "E_AEP_CONFLICT" not in results[loses[0]].get("message", ""):
        fail(f"expected the loser to get E_AEP_CONFLICT, got {results}")
    store = os.path.join(par_proj, "alva-air")
    gens = sorted(f for f in os.listdir(store) if f.startswith("gen-") and f.endswith(".air"))
    if len(gens) != 2:
        fail(f"expected 2 generations (no overwrite), got {gens}")
    run([alva, "project", "check", os.path.join(par_proj, "alva.toml")])
    log("  ok")

    # ---- 13. fuzz: arbitrary bytes never crash the AIR loader ----
    log("[11] fuzz: arbitrary AIR bytes never panic")
    import random as rnd
    rnd.seed(7)
    for i in range(150):
        size = rnd.randint(0, 512)
        blob = bytes(rnd.randrange(256) for _ in range(size))
        path = os.path.join(work, f"fuzz-{i}.air")
        with open(path, "wb") as fh:
            fh.write(blob)
        p = subprocess.run([alva, "air", "verify", path],
                           capture_output=True, text=True)
        if "panicked" in (p.stdout + p.stderr).lower():
            fail(f"fuzz input {i} panicked the loader")
    log("  ok")

    # ---- 14. lexical scope at real AST positions ----
    log("[12] lexical scope at real AST positions")
    scope_proj = os.path.join(work, "scope")
    os.makedirs(scope_proj)
    src = (
        '(module\n  (name "s")\n  (version "0.1.0")\n  (export f)\n'
        '  (fn f (params (param p (prim string))) (returns (prim string)) (pure)\n'
        '    (body\n'
        '      (let outer (string "o")\n'
        '        (let inner (concat (ref outer) (ref p))\n'
        '          (block\n'
        '            (if (bool true) (let then_b (string "t") (ref then_b)) (string "e"))\n'
        '            (fold i (range (int 0) (int 3))\n'
        '              (acc sum (prim string) (string ""))\n'
        '              (concat (ref sum) (ref outer)))))))))\n'
    )
    with open(os.path.join(scope_proj, "s.alva"), "w", encoding="utf-8") as fh:
        fh.write(src)
    with open(os.path.join(scope_proj, "alva.toml"), "w", encoding="utf-8") as fh:
        fh.write('[project]\nname = "s"\n\n[modules]\n"s" = "s.alva"\n')
    out = run([alva, "air", "export", os.path.join(scope_proj, "alva.toml"),
               "--out-dir", os.path.join(work, "scope-base")])
    air_file = os.path.join(work, "scope-base", "s.air")
    graph = json.loads(run([alva, "air", "view", air_file]))["nodes"]

    def find(kind, name=None):
        for n in graph:
            if n["kind"] == kind and (name is None or n["fields"].get("name") == name):
                return n
        return None

    outer = find("binding", "outer")
    inner = find("binding", "inner")
    then_b = find("binding", "then_b")
    fold = find("fold")
    assert outer and inner and then_b and fold, "fixture nodes not found"

    def candidates_at(air, parent_rev, slot):
        ed = Edit(alva, os.path.join(scope_proj, "alva.toml"))
        ed.ok({"op": "begin", "project": os.path.join(scope_proj, "alva.toml")})
        r = ed.ok({"op": "create_hole", "expected_type": "string", "allowed_effects": []})
        hole = r["result"]["revision"]
        ed.ok({"op": "replace_slot", "parent": parent_rev, "slot": slot, "child": hole})
        snap = os.path.join(work, f"scope-{parent_rev[:12]}-{slot}.air")
        ed.ok({"op": "snapshot", "path": snap})
        ed.send({"op": "abort"})
        ed.close()
        return run([alva, "hole", "candidates", snap, hole[:16]])

    # inner VALUE: inner not visible in its own value; outer and p are
    cands = candidates_at(air_file, inner["revision"], "value")
    if "ref outer" not in cands or "ref p" not in cands:
        fail(f"params/outer not visible in inner value:\n{cands}")
    if "ref inner" in cands:
        fail("binding leaked into its own value")

    # inner BODY: inner (itself), outer, p visible
    cands = candidates_at(air_file, inner["revision"], "body")
    for expect in ("ref outer", "ref inner", "ref p"):
        if expect not in cands:
            fail(f"{expect} missing in inner body:\n{cands}")

    # outer VALUE: outer and inner both invisible (not yet declared)
    cands = candidates_at(air_file, outer["revision"], "value")
    if "ref outer" in cands or "ref inner" in cands:
        fail("later/self binding leaked into outer value")
    if "ref p" not in cands:
        fail("param missing in outer value")

    # then_b BODY: then_b and outer visible
    cands = candidates_at(air_file, then_b["revision"], "body")
    if "ref then_b" not in cands or "ref outer" not in cands:
        fail(f"then_b body scope wrong:\n{cands}")

    # fold ACC_INIT: accumulator sum NOT visible; outer visible
    cands = candidates_at(air_file, fold["revision"], "acc_init")
    if "ref sum" in cands:
        fail("fold accumulator leaked into acc_init")
    if "ref outer" not in cands:
        fail("outer missing in fold acc_init")

    # fold BODY: accumulator sum visible
    cands = candidates_at(air_file, fold["revision"], "body")
    if "ref sum" not in cands:
        fail(f"fold accumulator missing in body:\n{cands}")
    log("  ok")

    # ---- 15. v0.6 Agent Runtime high-level tools ----
    log("[13] v0.6 Agent Runtime tools (no slot names, no .alva text)")
    ag_proj = os.path.join(work, "agent")
    shutil.copytree(os.path.join(root, "examples", "store_split"), ag_proj)
    run([alva, "air", "export", os.path.join(ag_proj, "alva.toml"),
         "--out-dir", os.path.join(work, "ag-base"), "--authoritative"])
    p = subprocess.Popen([alva, "agent"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)

    def atool(req_id, tool, **params):
        obj = {"request_id": req_id, "tool": tool}
        obj.update(params)
        p.stdin.write(json.dumps(obj) + "\n")
        p.stdin.flush()
        return json.loads(p.stdout.readline())

    r = atool("a1", "begin_transaction", project=os.path.join(ag_proj, "alva.toml"))
    if r.get("protocol_version") not in ("0.6", "0.7-replication") or not r.get("ok"):
        fail(f"agent begin failed: {r}")
    r = atool("a2", "inspect_project")
    if len(r["result"]["modules"]) != 10:
        fail("inspect_project modules wrong")
    r = atool("a3", "add_function", module="store.model", name="agent_hello",
              returns="string", params=[{"name": "x", "type": "string"}])
    if not r.get("ok"):
        fail(f"add_function failed: {r}")
    r = atool("a4", "inspect_function", name="store.model.agent_hello")
    if "param x" not in r["result"]["view"]:
        fail("inspect_function view wrong")
    r = atool("a5", "create_literal", type="string", value="hi from agent")
    lit = r["result"]["revision"]
    r = atool("a6", "append_step", function="store.model.agent_hello", step=lit)
    if not r.get("ok"):
        fail(f"append_step failed: {r}")
    r = atool("a7", "check_transaction")
    if not r.get("ok"):
        fail(f"check failed: {r}")
    r = atool("a8", "preview_semantic_diff")
    if "agent_hello" not in r["result"]["diff"]:
        fail("semantic diff missing agent_hello")
    r = atool("a9", "commit_transaction")
    if not r.get("ok"):
        fail(f"commit failed: {r}")
    atool("a10", "abort_transaction")
    p.stdin.close()
    p.wait()
    run([alva, "project", "check", os.path.join(ag_proj, "alva.toml")])
    log("  ok")

    log("ALL AIR/AEP HARDENING TESTS PASSED")


if __name__ == "__main__":
    main()
