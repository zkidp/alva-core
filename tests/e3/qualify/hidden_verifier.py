#!/usr/bin/env python3
"""Host-side hidden verifier for E3 candidates (zero-model, C1).

Runs against a COMMITTED authoritative store:
  1. `alva project check <alva.toml>` ALWAYS (E3 mandate; not a toggle).
  2. `alva build <alva.toml> --out-dir <scratch> --test` when
     checkspec["build_test"] is true (frozen command; error if true and the
     run fails).
  3. structural checks from the checkspec via the agent protocol
     (inspect_function + deterministic body-tree parsing).
  4. no-unrelated-changes: when baseline revisions are supplied, every
     function NOT in checkspec["allowed_touched"] must have an identical
     revision to the pristine baseline.

Usage: ALVA=<alva-exe> hidden_verifier.py <project-dir> <spec-dir>
where <spec-dir> contains checkspec.json and optionally baseline.json
({function_handle: revision}).
Exit: 0 = PASS, 1 = FAIL, 2 = usage/input error.
"""

import json
import os
import re
import subprocess
import sys
import tempfile


def fail(msg):
    print(f"VERIFIER FAIL: {msg}", flush=True)
    raise SystemExit(1)


class Agent:
    def __init__(self, alva, project_dir):
        env = dict(os.environ)
        env.pop("ALVA_AEP_ENABLE_E3_HIGH", None)  # LOW surface only
        env.setdefault("ALVA_AEP_ENABLE_EXPERIMENTAL_A1", "1")
        self.p = subprocess.Popen(
            [alva, "agent"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            text=True, encoding="utf-8", env=env,
        )
        self.toml = os.path.join(project_dir, "alva.toml")
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


def inspect(alva, project_dir, fn):
    a = Agent(alva, project_dir)
    a.ok("begin_transaction", project=a.toml)
    insp = a.ok("inspect_function", name=fn)
    a.close()
    return insp["result"]["revision"], insp["result"]["view"], insp["result"]["body"]


def call_segments(body, call_name):
    segs = []
    for m in re.finditer(
        rf"call name={re.escape(call_name)} rev=[0-9a-f]{{64}}", body):
        open_idx = body.rfind("(", 0, m.start())
        if open_idx < 0:
            continue
        depth, j = 0, open_idx
        while j < len(body):
            if body[j] == "(":
                depth += 1
            elif body[j] == ")":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        segs.append(body[open_idx:j + 1])
    return segs


def args_groups(seg):
    groups, pos = [], 0
    while True:
        gi = seg.find("args:", pos)
        if gi < 0:
            break
        gstart = gi + len("args:")
        d2, k = 0, gstart
        while k < len(seg):
            if seg[k] == "(":
                d2 += 1
            elif seg[k] == ")":
                d2 -= 1
                if d2 == 0:
                    break
            k += 1
        groups.append(seg[gstart:k + 1])
        pos = k + 1
    return groups


def literal_values(body):
    return re.findall(r"literal value=([^ )]+)", body)


def run_checks(alva, project_dir, checkspec, baseline):
    toml = os.path.join(project_dir, "alva.toml")
    # 1. project check ALWAYS (E3 mandate).
    p = subprocess.run([alva, "project", "check", toml],
                       capture_output=True, text=True)
    if p.returncode != 0:
        fail(f"project check failed:\n{p.stdout[-800:]}\n{p.stderr[-800:]}")
    # 2. build/test when explicitly requested (frozen command).
    if checkspec.get("build_test"):
        scratch = tempfile.mkdtemp(prefix="e3-build-")
        p = subprocess.run(
            [alva, "build", toml, "--out-dir", scratch, "--test"],
            capture_output=True, text=True)
        if p.returncode != 0:
            fail(f"build --test failed:\n{p.stdout[-800:]}\n{p.stderr[-800:]}")
    # 3. structural checks.
    for chk in checkspec.get("structural", []):
        kind = chk["kind"]
        if kind == "has_param":
            _, view, _ = inspect(alva, project_dir, chk["function"])
            line = re.search(rf"param {re.escape(chk['param'])}:\s*([^\n]+)",
                             view)
            if not line:
                fail(f"has_param: {chk['function']} lacks param "
                     f"{chk['param']}")
            if line.group(1).strip() != chk["type"]:
                fail(f"has_param: {chk['function']}.{chk['param']} type "
                     f"{line.group(1)!r} != {chk['type']!r}")
        elif kind == "call_arg_count":
            _, _, body = inspect(alva, project_dir, chk["function"])
            per_call = [args_groups(s)
                        for s in call_segments(body, chk["call_name"])]
            if not per_call:
                fail(f"call_arg_count: no call {chk['call_name']} in "
                     f"{chk['function']}")
            for gs in per_call:
                if len(gs) != chk["args"]:
                    fail(f"call_arg_count: {chk['function']} call "
                         f"{chk['call_name']} has {len(gs)} args, expected "
                         f"{chk['args']}")
        elif kind == "call_arg_literal":
            _, _, body = inspect(alva, project_dir, chk["function"])
            per_call = [args_groups(s)
                        for s in call_segments(body, chk["call_name"])]
            if not per_call:
                fail(f"call_arg_literal: no call {chk['call_name']} in "
                     f"{chk['function']}")
            for gs in per_call:
                idx = chk["arg_index"]
                if idx >= len(gs):
                    fail(f"call_arg_literal: {chk['function']} call "
                         f"{chk['call_name']} arg {idx} missing")
                m = re.search(r"literal value=([^ )]+)", gs[idx])
                if not m or m.group(1) != str(chk["value"]):
                    got = m.group(1) if m else "none"
                    fail(f"call_arg_literal: {chk['function']} call "
                         f"{chk['call_name']} arg {idx} value {got!r} != "
                         f"{chk['value']!r}")
        elif kind == "entity_exists":
            try:
                inspect(alva, project_dir, chk["entity"])
            except SystemExit:
                fail(f"entity_exists: {chk['entity']} missing")
        elif kind == "entity_absent":
            a = Agent(alva, project_dir)
            a.ok("begin_transaction", project=a.toml)
            r = a.call("inspect_function", name=chk["entity"])
            a.close()
            if r.get("ok"):
                fail(f"entity_absent: {chk['entity']} still present")
        elif kind == "function_effect":
            _, view, _ = inspect(alva, project_dir, chk["function"])
            m = re.search(r"\[(pure|io)\]", view)
            if not m or m.group(1) != chk["effect"]:
                got = m.group(1) if m else "none"
                fail(f"function_effect: {chk['function']} effect {got!r} != "
                     f"{chk['effect']!r}")
        elif kind == "body_call_count":
            _, _, body = inspect(alva, project_dir, chk["function"])
            n = len(call_segments(body, chk["call_name"]))
            if n != chk["count"]:
                fail(f"body_call_count: {chk['function']} has {n} calls to "
                     f"{chk['call_name']}, expected {chk['count']}")
        elif kind == "body_call_exists":
            _, _, body = inspect(alva, project_dir, chk["function"])
            if not call_segments(body, chk["call_name"]):
                fail(f"body_call_exists: {chk['function']} lacks call to "
                     f"{chk['call_name']}")
        elif kind == "body_literal_at":
            _, _, body = inspect(alva, project_dir, chk["function"])
            vals = literal_values(body)
            idx = chk["index"]
            if idx >= len(vals) or vals[idx] != str(chk["value"]):
                got = vals[idx] if idx < len(vals) else "none"
                fail(f"body_literal_at: {chk['function']}[{idx}] value "
                     f"{got!r} != {chk['value']!r}")
        elif kind == "body_literal_values":
            _, _, body = inspect(alva, project_dir, chk["function"])
            vals = literal_values(body)
            if vals != [str(v) for v in chk["values"]]:
                fail(f"body_literal_values: {chk['function']} has {vals!r}, "
                     f"expected {chk['values']!r}")
        elif kind == "body_step_count":
            _, _, body = inspect(alva, project_dir, chk["function"])
            n = body.count("steps:")
            if n != chk["count"]:
                fail(f"body_step_count: {chk['function']} has {n} steps, "
                     f"expected {chk['count']}")
        elif kind == "body_contains_kind":
            _, _, body = inspect(alva, project_dir, chk["function"])
            node_kind = chk["node_kind"]
            if f"({node_kind} " not in body:
                fail(f"body_contains_kind: {chk['function']} lacks "
                     f"{node_kind} node")
        elif kind == "body_literal_value":
            _, _, body = inspect(alva, project_dir, chk["function"])
            vals = literal_values(body)
            if not vals or vals[0] != str(chk["value"]):
                got = vals[0] if vals else "none"
                fail(f"body_literal_value: {chk['function']} value {got!r} "
                     f"!= {chk['value']!r}")
        else:
            fail(f"unknown structural check kind {kind!r}")
    # 4. no unrelated changes (revision preservation).
    allowed = set(checkspec.get("allowed_touched", []))
    for fn, base_rev in (baseline or {}).items():
        if fn in allowed:
            continue
        final_rev, _, _ = inspect(alva, project_dir, fn)
        if final_rev != base_rev:
            fail(f"untouched function {fn} changed: {base_rev[:12]} -> "
                 f"{final_rev[:12]}")
    print("VERIFIER PASS", flush=True)
    return 0


def main():
    if len(sys.argv) != 3:
        print("USAGE: hidden_verifier.py <project-dir> <spec-dir>",
              file=sys.stderr)
        return 2
    alva = os.environ.get("ALVA")
    if not alva:
        print("set ALVA to the alva executable", file=sys.stderr)
        return 2
    project, spec_dir = sys.argv[1], sys.argv[2]
    with open(os.path.join(spec_dir, "checkspec.json"), encoding="utf-8") as fh:
        checkspec = json.load(fh)
    baseline = None
    bpath = os.path.join(spec_dir, "baseline.json")
    if os.path.exists(bpath):
        with open(bpath, encoding="utf-8") as fh:
            baseline = json.load(fh)
    return run_checks(alva, project, checkspec, baseline)


if __name__ == "__main__":
    sys.exit(main())
