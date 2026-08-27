#!/usr/bin/env python3
"""Generate the 96 frozen run manifests (24 tasks x 2 arms x 2 reps).

Host-side prep ONLY. Reads candidate.json to extract the task statement,
group, verifier checkspec, and functions (for baseline revisions); the
formal runner never reads candidate.json. Each manifest is SHA-256'd into
MANIFEST-INDEX.json; the index hash is the frozen task-manifest-set hash.

Usage:
  ALVA=<alva-exe> python generate_run_manifests.py --out-dir <dir>
    [--candidates-dir <dir>] [--max-steps 200]
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


def sha256_file(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def baseline_revisions(alva, fixture_dir, functions):
    work = tempfile.mkdtemp(prefix="bl-")
    proj_dir = os.path.join(work, "proj")
    shutil.copytree(fixture_dir, proj_dir)
    toml = os.path.join(proj_dir, "alva.toml")
    env = dict(os.environ)
    env.pop("ALVA_AEP_ENABLE_E3_HIGH", None)
    env.setdefault("ALVA_AEP_ENABLE_EXPERIMENTAL_A1", "1")
    p = subprocess.Popen([alva, "agent"], stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, text=True, encoding="utf-8",
                         env=env)

    def call(tool, **kw):
        msg = {"request_id": "1", "tool": tool}
        msg.update(kw)
        p.stdin.write(json.dumps(msg) + "\n")
        p.stdin.flush()
        return json.loads(p.stdout.readline())

    call("begin_transaction", project=toml)
    out = {}
    for fn in functions:
        r = call("inspect_function", name=fn)
        if not r.get("ok"):
            raise RuntimeError(f"baseline inspect failed for {fn}: {r}")
        out[fn] = r["result"]["revision"]
    p.stdin.close()
    p.wait()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--candidates-dir",
                    default=os.path.join(os.path.dirname(HERE),
                                         "candidates"))
    ap.add_argument("--max-steps", type=int, default=200)
    args = ap.parse_args()
    alva = os.environ.get("ALVA")
    if not alva:
        sys.exit("set ALVA to the alva executable")
    os.makedirs(args.out_dir, exist_ok=True)
    index = []
    for cid in sorted(os.listdir(args.candidates_dir)):
        if not (cid[0] in "MN" and cid[1:].isdigit()):
            continue
        m = json.load(open(os.path.join(args.candidates_dir, cid,
                                        "candidate.json"),
                           encoding="utf-8"))
        base = baseline_revisions(
            alva, os.path.join(args.candidates_dir, cid, "fixture"),
            m.get("functions", []))
        for arm in ("LOW", "HIGH"):
            for rep in (1, 2):
                manifest = {
                    "task_id": cid,
                    "group": m["group"],
                    "arm": arm,
                    "rep": rep,
                    "task_statement": m["task_statement"],
                    "fixture": cid,
                    "max_tool_steps": args.max_steps,
                    "verifier_checkspec": m["verifier"],
                    "baseline_revisions": base,
                    "model": {},   # REQUIRED_INPUT filled at execution freeze
                }
                name = f"{cid}-{arm}-r{rep}.json"
                path = os.path.join(args.out_dir, name)
                with open(path, "w", encoding="utf-8") as fh:
                    json.dump(manifest, fh, indent=2)
                index.append({
                    "task_id": cid, "group": m["group"], "arm": arm,
                    "rep": rep, "manifest": name,
                    "sha256": sha256_file(path),
                })
    index_path = os.path.join(args.out_dir, "MANIFEST-INDEX.json")
    with open(index_path, "w", encoding="utf-8") as fh:
        json.dump({"count": len(index), "manifests": index}, fh, indent=2)
    print(f"wrote {len(index)} run manifests + MANIFEST-INDEX.json")
    print("index sha256:", sha256_file(index_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
